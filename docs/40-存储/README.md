# 40 — 存储（Longhorn / NFS / Longhorn webhook TLS / etcd 换盘）

> 资产：`/data1/ssdxt/storage/01~06` 脚本、`storage/crds/`（VolumeSnapshot CRD）、
> `storage/longhorn-webhook-tls-issue.md`（26KB 诊断报告）、`etcd-disk-requirement.md`。

---

## §1 Longhorn 1.13.0（2026-09-30 由 1.7.2 逐版本升级而来）

> 完整升级实录（版本链/镜像清单/踩坑/验证）：[longhorn-upgrade-1.7.2-to-1.13.0.md](longhorn-upgrade-1.7.2-to-1.13.0.md)。
> chart/values 资产：`/data1/ssdxt/charts/longhorn-upgrade/`；Harbor longhorn/ 共 71 个升级镜像（mirror.sh `longhorn-upgrade`）。

以下为 1.7.2 时代原始安装记录（镜像版本已随升级更新）：

**【原有功能】** Longhorn 用节点本地盘（`/data1/longhorn`）做分布式块存储，内置快照/备份/RWX。

**【后补调整 / 完整安装步骤】**

前置 ①：11 台节点装 open-iscsi（Longhorn 用 iSCSI 提供块设备）——脚本自动做。

前置 ②：镜像已由 WSL `mirror.sh longhorn` 搬进 Harbor（13 个：manager/engine/instance-manager/
share-manager/ui/backing-image-manager/support-bundle-kit + 6 个 CSI sidecar）。

前置 ③：**VolumeSnapshot CRD**（Longhorn 的 csi-snapshotter 需要，chart 不带）：
```bash
kubectl apply -f /data1/ssdxt/storage/crds/    # external-snapshotter 的 VolumeSnapshot CRD
```

安装（一键脚本）：
```bash
bash /data1/ssdxt/storage/03-longhorn-install.sh
```
脚本做的事：open-iscsi 前置 → `fix-chart-images.py` 把 chart 全部镜像改写为 Harbor →
写自定义参数（2 副本、`/data1/longhorn`、`concurrentReplicaRebuildPerNodeLimit: 1`
——100Mbps 网络下限流重建）→ `helm upgrade --install longhorn`。

```yaml
# 自定义参数（记录在案）
defaultSettings:
  defaultReplicaCount: 2
  defaultDataPath: /data1/longhorn
  concurrentReplicaRebuildPerNodeLimit: 1
persistence:
  defaultClass: true
  defaultClassReplicaCount: 2
```

**安装时踩过的 3 个阻塞问题（都是"改前现象→原因→解法"）**：
1. **fix-chart-images.py 双重前缀 bug**：早期版本对"无 registry 字段"的镜像会生成
   `harbor.wuxing.local/harbor.wuxing.local/longhorn/...` 双前缀（二次跑时 `harbor` 判断只看
   repository 是否含 'harbor'，但末段截取逻辑在嵌套结构下重复叠加项目名）。现象：镜像拉取
   404。解法：用修复后的脚本（`tools/fix-chart-images.py`，改写前先判断 `'harbor' not in repo`），
   且生成后**人工抽查** `/tmp/longhorn-values.yaml` 里 repository 是否恰好一层 Harbor 前缀。
   局限见 90-踩坑 §3。
2. **缺 chart**：longhorn-1.7.2.tgz 不在最早的 charts 目录里（当时只搬了 cilium/cert-manager/
   KPS），需先在 WSL `helm pull longhorn/longhorn --version 1.7.2` 并 scp 过去。
3. **缺 VolumeSnapshot CRD**：csi-snapshotter 反复报 CRD 未找到 → 前置 ③ 解决。

验证：
```bash
kubectl -n longhorn-system get pods          # 全部 Running（约 2~3 分钟）
kubectl get sc                               # longhorn (default)
kubectl -n longhorn-system get svc longhorn-frontend
# UI：kubectl -n longhorn-system port-forward svc/longhorn-frontend 8080:80
#   或 Gateway 域名 longhorn.wuxing.local（30-网络 §3）
# 冒烟：建 PVC 应 13 秒内 Bound
```

回滚：`helm uninstall longhorn -n longhorn-system && kubectl delete ns longhorn-system`
（确认无 PVC 引用后）。

---

## §2 Longhorn webhook TLS 问题（上游 #13012）+ 证书到期台账

**【原有功能】** Longhorn 内嵌 Rancher dynamiclistener 自动管理 webhook TLS Secret
（`longhorn-webhook-{ca,tls}`），正常情况下自动续期、无感。

**【后补调整】**

- **改前现象**：Secret `longhorn-webhook-tls` 的 resourceVersion 以 **~17 次/秒**增长；
  `secrets PUT code=409` 冲突 **192.8/s**（占全部写请求 **93%**）；apiserver 总请求 436/s；
  8 个 longhorn-manager pod 同时持有**两张不同 serial 的 leaf 证书**互相覆盖（fingerprint 来回翻转）；
  mutating 并发队列被打满（40~69，APF 上限 50）→ leases/CSI 流量被饿死，cilium-operator/
  Longhorn CSI 持续 leader-election 失租崩溃。
- **根因**：Longhorn 上游 [#13012](https://github.com/longhorn/longhorn/issues/13012)——
  多 manager 实例争抢同一 webhook TLS Secret 的自持循环：pod 启动时 dynamiclistener 本地 backing
  为空而 TLS 握手已到 → 生成全新证书写回 K8s → 集群里出现两个证书版本 → Merge 的
  prefer-additional 规则 + watch 延迟 → 互相回滚永不停息。本集群 apiserver/etcd 慢放大了启动竞争
  失败概率（正反馈：etcd 慢 → 竞争失败 → 抖动 → apiserver 更慢）。官方在 v1.12.0 修复并
  backport 到 v1.11.3；本环境 1.7.2 命中。
- **方案 A（已执行，2026-09-29）**：两个 Secret 加 static 注解 + 重启 ds：
  ```bash
  kubectl -n longhorn-system annotate secret longhorn-webhook-ca  listener.cattle.io/static=true --overwrite
  kubectl -n longhorn-system annotate secret longhorn-webhook-tls listener.cattle.io/static=true --overwrite
  kubectl -n longhorn-system rollout restart ds/longhorn-manager
  ```
  原理：`IsStatic` 让 dynamiclistener 的 Merge/AddCN/Renew/updateCert/saveInK8s 全部提前返回，
  任何 pod 不再写 Secret；证书仍经 watch 正常分发，webhook 继续可用。
- **验证（实测数据）**：
  ```bash
  # resourceVersion 60s 增量 0（修复前 +474/31s）
  kubectl -n longhorn-system get secret longhorn-webhook-tls -o jsonpath='{.metadata.resourceVersion}'; sleep 30
  kubectl -n longhorn-system get secret longhorn-webhook-tls -o jsonpath='{.metadata.resourceVersion}'
  # Prometheus：sum(rate(apiserver_request_total{resource="secrets",verb="PUT",code="409"}[5m])) → ≈0
  ```
  修复效果：secrets PUT 409 -100%、apiserver 总请求 485→15.7/s（-96.8%）、429 归零、
  mutating 队列 204→11；webhook 功能复验（`--dry-run=server` 正确拒绝非法 Volume）+
  新 PVC 13 秒 Bound，均通过。残余 CSI/cilium-operator 少量重启来自 etcd 磁盘（待换盘定位）。
- **✅ 方案 B（2026-09-30 已闭环）**：Longhorn 逐版本升级到 v1.13.0 后，移除两个 Secret 的 static 注解 +
  滚动重启 ds，官方修复（v1.12.0 修复 / backport v1.11.3）生效。实测：resourceVersion 10 分钟增量 **0**
  （15:03:05 rv=1815576 → 15:13:06 rv=1815576，ca 同样不变）；Prometheus `secrets PUT code=409` ≈0；
  apiserver 总请求 13.4/s；webhook `--dry-run=server` 正常拒绝非法 Volume。dynamiclistener 自动管理恢复，
  **"2027-08 手工轮转证书"待办作废**（由 Longhorn 自动续期接管）。
- **CSI 快照链路修复（同日）**：此前快照永远不 READYTOUSE 的根因有二，均已修复——
  ① 缺 snapshot-controller（VS→VSC 控制器）：已补 `storage/crds/rbac-snapshot-controller.yaml` +
  `storage/snapshot-controller.yaml`（镜像 longhorn/snapshot-controller:v8.0.1，SA 必须用专用
  snapshot-controller 而非 longhorn-service-account）；
  ② VolumeSnapshotClass 缺 `parameters: {"type": "snap"}` 时 1.7.2 把 CSI 快照当 backup 处理，
  无 backup-target 时报 missing input parameter——class 已带 type: snap。
  详见 [longhorn-upgrade-1.7.2-to-1.13.0.md](longhorn-upgrade-1.7.2-to-1.13.0.md) §3/§5。
- **历史备注——原"证书到期台账"（已作废）**：
  | 对象 | 到期日 | 处理期限 |
  |---|---|---|
  | leaf `longhorn-webhook-tls` | **2027-09-29** | **2027-08 前必须手工轮转** |
  | CA `longhorn-webhook-ca` | 2036-09-26 | 远期 |
  轮转方法（届期执行）：先备份 → 移除两个 static 注解 → `rollout restart ds/longhorn-manager`
  触发重签；更稳妥是届时升级到 ≥v1.11.3 用官方轮转机制（方案 B）。
  备份：`/data1/ssdxt/storage/backup/longhorn-webhook-secrets-0929-1610.yaml`。
- **回滚**：`annotate ... listener.cattle.io/static-` 两个 Secret + 重启 ds（抖动会回来，仅排障用）。

---

## §3 NFS（plant02，/data1/k8s-nfs，933G）

**【原有功能】** plant02（10.100.10.31）跑 nfs-kernel-server，导出 `/data1/k8s-nfs` 给 10.100.10.0/24
（rw,sync,no_subtree_check,no_root_squash），供"大容量、不需副本"场景（日志归档、备份落地）。

**【操作】**（已执行过，脚本幂等）
```bash
bash /data1/ssdxt/storage/01-nfs-server-plant02.sh    # 在 plant02：装 nfs-kernel-server + exports
bash /data1/ssdxt/storage/02-nfs-client-nodes.sh      # 11 台节点装 nfs-common
showmount -e 10.100.10.31                             # 验证导出列表
```
注意：nfs-subdir-external-provisioner 镜像已备（`nfs-provisioner/nfs-subdir-external-provisioner:v4.0.2`），
如需动态供给再装；当前默认 SC 是 longhorn，NFS 用静态 PV。

回滚：plant02 `exportfs -ra` 移除导出行；节点 `apt-get remove nfs-common`。

---

## §4 etcd 换盘验收标准 + 迁移脚本

**【原有功能】** etcd 数据在系统盘 `/var/lib/etcd`（虚拟化共享存储池）。

**【后补调整】（尚未执行——高性能盘到位后按此闭环）**

- **验收标准**（fio **3 台同时**跑，排除共享争抢；etcd 模式必须 `--direct=0 --fdatasync=1`，
  `--direct=1` 测出的是假数据）：
  | 指标 | 达标线 | 当前实测（不达标） |
  |---|---|---|
  | 同步写 IOPS（8k+datasync） | **≥1000/s** | 25~243/s |
  | fdatasync p99 | **≤10ms** | 8~37ms |
  | fdatasync p99.9 | **≤50ms** | 616ms~2.1s |
- **fstab 纪律**：用 **UUID**（不要设备名）；**不加 nofail**（盘没挂上要 fail-fast，让 systemd 拦住 etcd）；
  并配 systemd 挂载依赖 `RequiresMountsFor=/var/lib/etcd`。
- **迁移脚本**（滚动、业务不中断，一次只动一台）：
  ```bash
  bash /data1/ssdxt/storage/05-etcd-migrate-to-fastdisk.sh check           # 只做 fio 验收
  bash /data1/ssdxt/storage/05-etcd-migrate-to-fastdisk.sh prepare 10.100.10.10   # 格式化 xfs + 挂 /mnt/etcd-new + rsync 数据
  bash /data1/ssdxt/storage/05-etcd-migrate-to-fastdisk.sh cutover 10.100.10.10   # 停 etcd→备份→增量同步→挂 /var/lib/etcd→fstab(UUID,无nofail)→RequiresMountsFor→起 etcd
  # 三台完成后：
  bash /data1/ssdxt/storage/05-etcd-migrate-to-fastdisk.sh restore-timers  # 恢复 20-系统层 §2 的 2.5s/250ms 与各组件租约
  ```
  安全设计：check 不达标直接退出；cutover 前自动 tar 备份原数据目录到
  `/data1/ssdxt/storage/backup/`；每台之间人工回车确认。
- **验证**：cutover 后 `endpoint health` 三台全绿；`df -h /var/lib/etcd` 指向新盘；
  24h 后 `journalctl -u etcd | grep -c 'slow fdatasync'` = 0。
- **回滚**：`mv /var/lib/etcd /var/lib/etcd.new && mv /var/lib/etcd.old-<ts> /var/lib/etcd`
  + 还原 fstab + `systemctl start etcd`。

---

## §5 Longhorn UI Basic Auth（nginx 反代，2026-09-30 落地）

UI 默认无认证，经 Gateway 暴露必须补：nginx Basic Auth 反代（`wxq-` 前缀资源，不碰 longhorn 组件），
HTTPRoute `longhorn-route` 后端已切 `wxq-longhorn-auth-proxy:80`。凭据在 control-01
`/data1/ssdxt/storage/longhorn-ui-credentials.txt`（600）；**回滚=路由后端改回 `longhorn-frontend`**。
全文（方案/踩坑/重置/回滚）：[longhorn-ui-auth.md](longhorn-ui-auth.md)。
