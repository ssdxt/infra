#!/bin/bash
# Insert §0 (fix + cert expiry ledger) and append §7 (etcd monitoring blind spot) into the issue doc
set -eu
DOC=/data1/ssdxt/storage/longhorn-webhook-tls-issue.md
cp -a $DOC $DOC.bak.$(date +%m%d-%H%M%S)
echo "backup: $DOC.bak.*"

python3 - <<'PY'
doc = '/data1/ssdxt/storage/longhorn-webhook-tls-issue.md'
s = open(doc, encoding='utf-8').read()

anchor = '- 本次仅诊断，**未做任何变更**\n\n---\n'
section0 = '''- 诊断阶段为只读；**方案 A 已于 2026-09-29 16:11 经批准后执行**（见 §0）

---

# ⚠️ §0 证书到期台账（最高优先级，请登记到运维日历）

方案 A 给两个 Secret 打上了 `listener.cattle.io/static="true"`，**dynamiclistener 从此不再自动续期**。必须手工轮转；忘记的后果是 **webhook TLS 证书过期 → Longhorn admission webhook 全量失败（failurePolicy=Fail）→ 无法创建/修改任何 Longhorn CR**。

| 对象 | 备份文件 | 生效日 | **到期日** | 处理期限 |
|---|---|---|---|---|
| **leaf 证书** `longhorn-system/longhorn-webhook-tls` | `storage/backup/longhorn-webhook-leaf-0929-1610.pem` | 2026-09-29 | **2027-09-29** | **必须在 2027-08 之前完成轮转**（留 1 个月缓冲） |
| **CA 证书** `longhorn-system/longhorn-webhook-ca` | `storage/backup/longhorn-webhook-ca-0929-1610.pem` | 2026-09-29 | **2036-09-26** | 2036 年（远期，可忽略） |

- leaf 有效期 365 天，CA 有效期 10 年。
- 两个 Secret 的完整 yaml 备份：`/data1/ssdxt/storage/backup/longhorn-webhook-secrets-0929-1610.yaml`
- **轮转方法（届期执行）**
  1. 先备份：`kubectl -n longhorn-system get secret longhorn-webhook-ca longhorn-webhook-tls -o yaml > backup.yaml`
  2. 移除 static 注解、让 dynamiclistener 恢复自动签发：
     `kubectl -n longhorn-system annotate secret longhorn-webhook-ca listener.cattle.io/static-`
     `kubectl -n longhorn-system annotate secret longhorn-webhook-tls listener.cattle.io/static-`
  3. 重启 manager 触发重签：`kubectl -n longhorn-system rollout restart ds/longhorn-manager`
  4. **注意**：这样做会**把 §1 的抖动问题带回来**。更稳妥的路线是届时直接升级到已修复的 Longhorn（≥ v1.11.3），或按 §3 方案 C 用 helm 预置长有效期静态证书。

## §0.1 方案 A 执行结果（2026-09-29 16:11~16:28）

```bash
kubectl -n longhorn-system annotate secret longhorn-webhook-ca  listener.cattle.io/static=true --overwrite
kubectl -n longhorn-system annotate secret longhorn-webhook-tls listener.cattle.io/static=true --overwrite
kubectl -n longhorn-system rollout restart ds/longhorn-manager
```

| 指标 | 修复前 | 修复后（干净窗口 16:19） | 变化 |
|---|---|---|---|
| Secret `resourceVersion` 60s 增量 | **+474 / 31s（≈15 写/秒）** | **0 / 60s** | **抖动完全停止** |
| `secrets PUT` code=409 | 210.8 /s | **0 / s** | **-100%** |
| `secrets PUT` code=200（提交=etcd 写入） | 12.7 /s | **0.0037 /s** | **-99.97%** |
| 全部 apiserver 请求 | 485 /s | **15.7 /s** | **-96.8%** |
| 全部写请求 | 216 /s | **5.0 /s** | **-97.7%** |
| mutating 队列深度（5m max） | **204** | **11** | **-95%** |
| `429` terminations（secrets） | 1166 / 10m | **0 / 5m** | **归零** |
| static 注解存活 | — | 2/2（3 次采样） | 未被覆盖 |

功能复验（均通过）：
- **admission webhook 正常**：`kubectl apply --dry-run=server` 造非法 Volume 仍被正确拒绝 → `The request is invalid: : invalid volume frontend specified:`（证明证书分发到 8 个 pod 正常、webhook 未损坏）
- **Longhorn 数据面正常**：新建 1Gi PVC（storageClass=longhorn）**13 秒内 Bound**（`pvc-e33db8b9-…`），验完已清理
- `longhorn-manager` DaemonSet 滚动完成 8/8；longhorn 47 个 Pod 全部 Running、无异常

残余观察（8 分钟静默期，用 `restartCount` 正确统计）：

| 组件 | 修复前崩溃（<15min） | 修复后 8 分钟增量 |
|---|---|---|
| CSI（provisioner/attacher/resizer/snapshotter） | 3 | **+2** |
| cilium-operator | 2 | **+1** |

→ **未完全归零**。但此时 apiserver 总请求已降到 15/s、429 归零、mutating 队列 1~11，说明**应用层压力已消除，残余抖动来自基础设施层**（etcd 磁盘 fsync 延迟，见 `etcd-disk-requirement.md`）。需在 etcd 监控打通后（§7）继续定位。

---
'''

assert anchor in s, 'anchor for section 0 not found'
s = s.replace(anchor, section0, 1)

section7 = '''

---

# §7 附：etcd 监控盲区诊断（Prometheus 里 etcd 指标 0 series）

> 本节为**只诊断、未做任何变更**。结论：**etcd 监控从未配置成功**，不是回归。这是长期盯 etcd 健康（尤其磁盘 fsync 延迟）的关键缺口。

## 7.1 结论（一句话）
本集群的 etcd 是 **systemd 服务（不是 kubeadm 静态 pod）**，而 kube-prometheus-stack 的 etcd ServiceMonitor 依赖「发现带 `component=etcd` 标签的 **Pod/Endpoint**」。既然 etcd 没有 Pod，端点发现结果为 0 → Prometheus 一个 target 都没有 → **0 series**。同时该 SM 默认按 `scheme: http` 抓 `2381` 端口，而本集群 etcd 只监听 `2379/2380` 且强制 mTLS，即使有端点也抓不通。

## 7.2 证据链（全部实测）

**① etcd 根本没有 Pod —— 这是最根本的一条**
```
$ kubectl -n kube-system get pods -l component=etcd
No resources found in kube-system namespace.
```

**② Service 的 selector 匹配不到任何对象**
```
Service prometheus-stack-kube-prom-kube-etcd (kube-system)
  selector:            component: etcd        ← 匹配 0 个 Pod
  ports:               name=http-metrics  port=2381  targetPort=2381
  clusterIP:           None (headless)
```

**③ EndpointSlice 是空的**
```
EndpointSlice prometheus-stack-kube-prom-kube-etcd-4bmbh
  addressType: IPv4
  endpoints:   null      ← 没有任何地址
  ports:       null
```

**④ Prometheus 侧：job 存在但 0 个 target**
```
scrape config 里有 16 个 job，其中包含：
  serviceMonitor/monitoring/prometheus-stack-kube-prom-kube-etcd/0
     kubernetes_sd_configs: role=endpoints, namespaces=[kube-system]
     keep: __meta_kubernetes_service_label_app=kube-prometheus-stack-kube-etcd
     keep: __meta_kubernetes_endpoint_port_name=http-metrics
     scheme=http  metrics_path=/metrics  tls_config=None  bearer=None
active targets 里：apiserver/scheduler/controller-manager/kubelet 等都有 target，
但 "does an etcd job appear among active targets? False"  ← etcd 一个 target 都没有
```
→ 说明 ServiceMonitor **生效了**（Prometheus 配置里有这个 job），但**发现不到任何端点**，所以永远不产生样本。

**⑤ etcd 实际是 systemd 服务**
```
$ systemctl is-active etcd   → active
$ systemctl cat etcd
  # /etc/systemd/system/etcd.service
  ExecStart=/usr/local/bin/etcd
  EnvironmentFile=/etc/etcd.env
  Type=notify

$ ls /etc/kubernetes/manifests/
  kube-apiserver.yaml  kube-controller-manager.yaml  kube-scheduler.yaml  kube-vip.yaml
  ← 注意：没有 etcd.yaml（apiserver/scheduler/controller-manager 三个 SM 能采到，
     正是因为它们是静态 Pod；etcd 不是，所以采不到）
```

**⑥ 端口对不上：etcd 只有 2379/2380，没有 2381**
```
10.100.10.10 / .14 / .19   listeners on 2381 = 0   (三台都是 0)
ss 显示：
  127.0.0.1:2379, <node-ip>:2379   (client)
  <node-ip>:2380                   (peer)
/etc/etcd.env:
  ETCD_LISTEN_CLIENT_URLS=https://localhost:2379,https://10.100.10.10:2379
  ETCD_LISTEN_PEER_URLS=https://10.100.10.10:2380
  ETCD_CLIENT_CERT_AUTH=true                ← 强制客户端证书
  ETCD_CERT_FILE=/etc/ssl/etcd/ssl/server.crt
  ETCD_TRUSTED_CA_FILE=/etc/ssl/etcd/ssl/ca.crt
etcd 版本：3.7.0（其 --listen-metrics-urls 参数受支持）
```

**⑦ 就算端点存在，当前配置也抓不通（协议/证书层面）**
```
从 prometheus pod 里直接访问（无客户端证书）：
  https://10.100.10.10:2379/health → TLS error from peer (alert code 40): handshake failure
即 SM 的 scheme=http + tls_config=None 无法访问一个强制 mTLS 的 HTTPS 端口。

monitoring / kube-system 命名空间内都没有 etcd 客户端证书 Secret
（kube-prometheus-stack 的 etcd 采集需要额外的 client cert secret，本集群从未创建）
```

**⑧ 反证：带客户端证书就能拿到全部指标（说明修法可行）**
```
$ curl --cacert /etc/kubernetes/pki/etcd/ca.crt \
       --cert  /etc/kubernetes/pki/etcd/client.crt \
       --key   /etc/kubernetes/pki/etcd/client.key  https://10.100.10.10:2379/metrics
etcd_server_has_leader 1
etcd_disk_wal_fsync_duration_seconds_count 995660
etcd_mvcc_db_total_size_in_bytes 3.9145472e+07
etcd_server_proposals_committed_total 2.082454e+06
```
→ 这些正是盯 etcd 健康最需要的指标（含 fsync 延迟、db 大小、proposals、leader）。

## 7.3 影响
目前 **完全看不到 etcd 的任何指标**：`etcd_disk_wal_fsync_duration_seconds`（磁盘 fsync 延迟）、`etcd_mvcc_db_total_size_in_bytes`（db 增长）、`etcd_server_proposals_committed_total`（写入 QPS）、`etcd_server_leader_changes_seen_total`（leader 抖动）全部缺失。也就是说 `etcd-disk-requirement.md` 里关于"etcd 磁盘慢"的判断**没有 Prometheus 数据支撑**，只能靠外部手段观测。修好这条对定位 CSI/cilium-operator 的残余抖动也有直接价值。

## 7.4 修法建议（**均需先批准，本次未执行**）

**方案 ①（推荐）不动 etcd，改成「静态端点 + mTLS」采集**
1. 把控制面的客户端证书做成 Secret（monitoring 命名空间），例如 `kube-etcd-client-certs`：
   `ca.crt` ← `/etc/kubernetes/pki/etcd/ca.crt`，`etcd-client.crt` ← `.../client.crt`，`etcd-client.key` ← `.../client.key`
2. 因为 etcd 没有 Pod，Service 用 selector 永远发现不到端点 → **必须手工建一个 EndpointSlice/Endpoints 对象**，指向 `10.100.10.10:2379`、`10.100.10.14:2379`、`10.100.10.19:2379`，**端口名必须是 `http-metrics`**（SM 的 relabel 用这个名字做 keep）。
3. 改 ServiceMonitor `prometheus-stack-kube-prom-kube-etcd` 的 endpoint：`scheme: https`、`tlsConfig: {caFile, certFile, keyFile, serverName}`、`insecureSkipVerify: false`。
- **风险**：低。不重启 etcd、不碰控制面。
- **代价**：需要改 kube-prometheus-stack 的配置（ServiceMonitor）——按当前约定需要单独批准。

**方案 ② 让现有 SM 原样可用（改动最小，但要重启 etcd）**
1. 三台控制面 `/etc/etcd.env` 增加 `ETCD_LISTEN_METRICS_URLS=http://0.0.0.0:2381`，逐个（滚动）重启 etcd。
2. 手工建 Endpoints 指向 3 个 IP 的 `2381`，端口名 `http-metrics`。
- **风险**：中。要**重启 etcd**（控制面组件，需逐台滚动并观察 etcd 健康）；且把明文 metrics 端口暴露在内网（建议配合防火墙/网络策略限制来源）。
- **好处**：监控侧几乎不用改（保持 `scheme: http` + 2381，与 chart 默认一致）。

**方案 ③ 部署独立的 etcd exporter（DaemonSet/Deployment）**
- **风险**：低（不碰 etcd、不碰监控栈现有配置），但离线环境需要搬新镜像并维护额外组件。
- **适用**：如果不想改 ServiceMonitor、也不想动 etcd 时的折中。

**推荐 ①**：不动 etcd、不重启控制面，风险最低，且能立刻补齐 fsync 延迟等关键指标。
'''

s = s.rstrip() + section7
open(doc, 'w', encoding='utf-8').write(s)
print('doc updated, new size:', len(s.encode('utf-8')))
PY

echo "--- head ---"
sed -n '1,20p' $DOC
echo "..."
echo "--- section list ---"
grep -n '^# \|^## ' $DOC | head -40
