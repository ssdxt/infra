# containerd 数据目录迁移 /data1/containerd — 方案（未执行）

> 状态：**方案 only**，等维护窗口。脚本：`/data1/ssdxt/storage/08-containerd-relocate.sh`（已上传 control-01）。
> 背景：worker 根盘 48G 曾达 71~78%（/var/lib/containerd 镜像 25G+）。一期已做 kubelet imageGC
> 阈值调优 + 每周 `crictl rmi --prune` 兜底（见 [README §8](README.md)）；若后续镜像量仍挤压根盘，
> 再启用本方案，把 containerd 的 `root` 迁到 931G 的 /data1。

---

## 1. 脚本做什么（幂等，逐台）

在**目标节点**上执行，一次一台：

```bash
# 先 scp 脚本到目标节点（control-01 上）：
scp /data1/ssdxt/storage/08-containerd-relocate.sh root@<节点IP>:/data1/ssdxt/storage/

# 然后登目标节点：
bash /data1/ssdxt/storage/08-containerd-relocate.sh check      # ① 预检（空间/文件系统），不改动
bash /data1/ssdxt/storage/08-containerd-relocate.sh migrate    # ② 迁移
bash /data1/ssdxt/storage/08-containerd-relocate.sh status     # ③ 查看状态
bash /data1/ssdxt/storage/08-containerd-relocate.sh rollback   # 出问题回滚
```

migrate 流程：备份 config.toml（`.bak.relocate.日期`）→ `kubectl drain`（经 ssh 到 control-01）→
停 kubelet + containerd → `rsync -a /var/lib/containerd/ /data1/containerd/` + 文件数校验 →
改 `root = "/data1/containerd"` → 旧目录改名 `.old.日期` 保留 → 起服务 → 等 Ready + Pod 全 Running
→ `uncordon` → 落标记文件。任一步失败自动 rollback。**前一台稳定 30 分钟再做下一台。**

## 2. 与 Longhorn 共用 /data1 的影响分析

| 维度 | 影响 | 结论 |
|---|---|---|
| **空间** | Longhorn 副本当前占用有限、/data1 有 931G；containerd 镜像层 + 容器 writable 层迁入后两者竞争同一池。镜像增长是慢变量，Longhorn 副本随业务涨。 | 931G 下风险低，但**必须**有容量巡检（三规矩①） |
| **IOPS** | /data1 是单块盘：镜像拉取（解压写大量小文件）与 Longhorn 副本落盘（随机写 + 还原时全量读）互相抢 IO。最坏场景：节点同时被调度的 Pod 冷启动（大量读镜像层）+ Longhorn rebuild → 双方都慢。 | 可接受；避免在 Longhorn rebuild 期间做迁移和大规模拉镜像 |
| **Longhorn 水位自保** | Longhorn 1.13 有 StorageOverProvisioning/StorageMinimalAvailablePercentage 机制，磁盘水位过高会自动停止往该节点调度副本（`Scheduling` 失败、副本卡 Unscheduled）。containerd 占用会挤占 Longhorn 的可调度空间估算。 | 迁移前**必须核对** Longhorn node disk 的 `StorageReserved`/水位参数（三规矩③），确保 containerd 用量被计入同一块盘的 available（Longhorn 读的是文件系统统计，默认会正确反映） |
| **故障域** | /data1 盘故障 = 业务数据副本 + 容器运行时同时丢。 | 该盘故障本身就是节点级灾难（节点重建），containerd 目录丢失可重建，Longhorn 其他副本兜底——无新增单点 |

## 3. 三条规矩（迁移完成后立即生效）

### ① 容器目录容量巡检 cron（必装）

```bash
# /etc/cron.d/wxq-containerd-size —— 每小时巡检，du 超 250G 告警 + 清最老未使用镜像
0 * * * * root S=$(du -sg /data1/containerd 2>/dev/null | awk '{print $1}'); \
  [ "$S" -gt 250 ] && { echo "$(date) containerd=${S}G 超阈值" >> /var/log/wxq-containerd-size.log; \
  crictl rmi --prune >> /var/log/wxq-containerd-size.log 2>&1; }
```
（250G = 根盘老目录实测峰值的 10 倍缓冲；`crictl rmi --prune` 只删无容器引用的镜像，安全。）
告警通道暂用日志文件；后续可接 node_exporter textfile collector 进 Prometheus。

### ② kubelet imageGC 在 /data1 上会失效 — 必须知道

kubelet 的 imageGC（一期配的 70/60 阈值）**只统计并保护 kubelet 认为的节点文件系统**，即
kubelet 启动时识别的 rootfs 分区（/var/lib/kubelet 所在盘）。containerd root 迁到 /data1 后：

- 镜像占的是 /data1 的空间，而 kubelet 监控的是 / 分区 → **镜像涨爆 /data1 时 imageGC 永远不触发**；
- 反过来，/data1 被镜像 + Longhorn 双方写入，kubelet 的 eviction（按 / 分区算）也管不到它。

所以迁移后，**磁盘保护责任完全移交三规矩①的 cron 巡检**；一期的 imageGC 保留（仍保护 / 分区上
其余增长，如日志/emptyDir），但不再是镜像的主要防线。

### ③ Longhorn 磁盘水位设置核对（迁移前后各做一次）

```bash
kubectl -n longhorn-system get nodes.longhorn.io <节点名> -o yaml | grep -A8 'diskStatus'
# 关注：StorageAvailable 是否已把 /data1/containerd 占用扣掉（Longhorn 读文件系统统计，应自动反映）
kubectl -n longhorn-system get setting storage-minimal-available-percentage -o jsonpath='{.value}'
kubectl -n longhorn-system get setting storage-over-provisioning-percentage -o jsonpath='{.value}'
```
要求：MinimalAvailable ≥ 20（默认 25）；若调过低，迁移后 /data1 满盘会同时打爆 Longhorn 副本写和容器运行时。

## 4. 回滚方法

脚本自带：`bash 08-containerd-relocate.sh rollback`，等价于手工：

```bash
kubectl drain <节点> --ignore-daemonsets --delete-emptydir-data   # （control-01 上）
systemctl stop kubelet containerd
cp -a /etc/containerd/config.toml.bak.relocate.<日期> /etc/containerd/config.toml   # root 改回
rsync -a /data1/containerd/ /var/lib/containerd.old.<日期>/     # 新目录期间的增量合回
rm -rf /data1/containerd && mv /var/lib/containerd.old.<日期> /var/lib/containerd
systemctl start containerd kubelet
kubectl uncordon <节点>
```

## 5. 验收清单（每台迁移后）

- [ ] `grep '^root' /etc/containerd/config.toml` → `/data1/containerd`
- [ ] `ctr -n k8s.io images ls -q | wc -l` 镜像数与迁移前一致
- [ ] 节点 Ready；该节点 Pod 全部 Running/Completed，无重启增加
- [ ] `df -h /` 根盘使用率较迁移前下降（镜像层搬走）
- [ ] `df -h /data1` 增量 ≈ 原镜像占用；Longhorn 副本仍健康（`longhorn` UI / `kubectl -n longhorn-system get volumes`）
- [ ] 稳定 1 周后删除 `/var/lib/containerd.old.<日期>` 回收根盘空间
