# etcd 高性能盘迁移实录（2026-09-30 已执行）

> 本文是实际执行记录，补充 40-存储/README.md 的验收标准。执行脚本：`/data1/ssdxt/storage/05b-etcd-cutover-executed.sh`

## 一、背景与磁盘验收

虚拟化方为三台 control 各加 50G 盘（/dev/sdb）。**fio 验收未达原定 1000 IOPS 基线**：
- 实测（三台同时，8k 写 + fdatasync）：IOPS **388~433**，p99 fsync **24~27ms**，p99.9 **54~64ms**
- 对照旧盘：25~243 IOPS，p99.9 **616ms~2.1s**
- 判定：未达标但**尾延迟改善 10~30 倍**（对 etcd 最关键的恰是尾延迟），经用户知情决策继续迁移

⚠️ 教训：`.10` 的新盘被（虚拟化方）预先格式化并挂载为 `/data2`——迁移脚本内做了清理：umount /mnt 重复挂载、umount /data2、清除 fstab /data2 行。

## 二、执行过程（逐台滚动，零中断）

每台顺序：tar 备份数据目录 → 停 etcd → rsync 数据到新盘 → 新盘挂到 `/var/lib/etcd`（fstab UUID、**无 nofail**）→ systemd drop-in `RequiresMountsFor` → 启动 → 健康验证 → 下一台。

| 节点 | 数据量 | 恢复耗时 | 结果 |
|---|---|---|---|
| 10.100.10.10 | 477M | 5s 健康 | ✅ |
| 10.100.10.14 | 454M | 5s 健康 | ✅ |
| 10.100.10.19 | 455M | 5s 健康 | ✅ |

**保险措施**（全部在位）：
- 全局快照：三台各一份 `/root/etcd-snap-0930-0921.db`
- 数据备份：`/root/etcd-data-bak-0930-0921.tar.gz`（每台）
- 旧目录：`/var/lib/etcd.old-0930-0921`（观察一周后可删）
- 脚本内置自动回滚（60s 未健康 → 还原旧目录重启）

## 三、效果（立竿见影）

| 指标 | 迁移前 | 迁移后（稳态） |
|---|---|---|
| slow fdatasync | 112~255 条/**小时** | **0 条**（.19 有 3 条为迁移回放尾迹） |
| cilium-operator 崩溃 | 300+ 次，持续 | **停止**（5 分钟观察窗零新增） |
| Longhorn CSI 全家桶 | 46~121 次，持续 | **停止** |
| kube-state-metrics | 135 次 | **停止** |
| KubePodCrashLooping 告警 | firing | **消失** |
| KubeAPIErrorBudgetBurn | critical ×2 + warning ×2 | critical **消失**，warning 衰减中（1h/6h 窗口） |

## 四、租约参数恢复（同日执行）

换盘目的达成后，把绕行慢盘的临时参数全部调回正常：

| 组件 | 绕行值 | 已恢复为 | 位置 |
|---|---|---|---|
| etcd | 选举 10000ms / 心跳 500ms | **2500 / 250** | /etc/etcd.env（逐台滚动重启，备份 .bak.*） |
| kube-vip | 30 / 20 / 5 | **15 / 5 / 2** | /etc/kubernetes/manifests/kube-vip.yaml（python 改） |
| controller-manager | 60s / 40s / 5s | **15s / 10s / 2s** | 静态清单 --leader-elect-* |
| scheduler | 同上 | 同上 | 同上 |

三台滚动执行，每台改完验证 Pod Running 与 etcd 健康。恢复后 5 分钟观察窗同样**零新增崩溃**。

## 五、遗留

1. **磁盘本身仍非"本地 SSD"级**（400 IOPS 共享层）——比旧盘好一个量级，够 etcd 当前规模；若未来集群规模大增（数万对象），可再向虚拟化方提级
2. etcd 监控打通（方案①）仍未做——换盘后 fsync p99 应已达标，接上监控即可用数据确认
3. adapter CPUThrottlingHigh（info）仍在：CPU limit 1 核下 relist 期仍 ~42% 限流，如在意提到 2 核
4. 观察 7 天后可删除旧数据目录 `/var/lib/etcd.old-*`
