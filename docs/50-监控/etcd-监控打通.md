# etcd 监控打通实录（方案①：静态 Endpoints + mTLS，2026-09-30 已执行）

> 执行脚本：`/data1/ssdxt/monitoring/04-etcd-monitoring.sh`（幂等）
> 清单：`/data1/ssdxt/monitoring/manifests/04-etcd-monitoring.yaml`
> 前置背景：[50-监控/README.md §4 盲区](README.md)、[40-存储/etcd换盘迁移实录.md](../40-存储/etcd换盘迁移实录.md)

## 一、根因回顾

本集群 etcd 是 **systemd 服务**（kk v4.0.7 安装形态，非静态 Pod），三台 10.100.10.10/.14/.19，
只监听 2379(client)+2380(peer) 且 2379 强制 mTLS。kube-prometheus-stack 62.7.0 自带的
`prometheus-stack-kube-prom-kube-etcd` Service（selector `component=etcd`）与 ServiceMonitor
因此**双重失效**：

1. Service 靠 label 匹配 **Pod** → systemd 形态下永远匹配 0 个 → EndpointSlice 空 → 无 target；
2. 即使有端点，SM 默认 `scheme: http` 抓 2381（本集群无此端口），mTLS 也过不去。

修法采用**方案①（不动 etcd）**：自建无 selector Service + 手工 Endpoints 直指三台 IP:2379 +
自建 SM（https + 客户端证书）。反证可行：带 `/etc/kubernetes/pki/etcd/` 客户端三件套
curl `https://IP:2379/metrics` 可取全部指标。

## 二、实施细节（全部已执行）

### 1. 证书 Secret + 备份

```bash
mkdir -p /data1/ssdxt/monitoring/backup/etcd-certs
cp -a /etc/kubernetes/pki/etcd/{ca.crt,client.crt,client.key} /data1/ssdxt/monitoring/backup/etcd-certs/
kubectl -n monitoring create secret generic kube-etcd-client-certs \
  --from-file=ca.crt=/etc/kubernetes/pki/etcd/ca.crt \
  --from-file=client.crt=/etc/kubernetes/pki/etcd/client.crt \
  --from-file=client.key=/etc/kubernetes/pki/etcd/client.key --dry-run=client -o yaml | kubectl apply -f -
```

### 2. 自建三件套（不归 helm 管，不碰 chart 自带的那对）

`manifests/04-etcd-monitoring.yaml`，要点：

- **Service `etcd-monitor`**：无 selector、headless（`clusterIP: None`），port 名**必须叫
  `http-metrics`**（SM 靠它定位端口）、port 2379；
- **Endpoints `etcd-monitor`**：静态子集 10.100.10.10 / .14 / .19:2379；
- **ServiceMonitor `etcd-monitor`**：label `release: prometheus-stack`
  （对齐 Prometheus CR 的 `serviceMonitorSelector.matchLabels`）+ `monitoring: etcd` 供自选；
  `scheme: https`，`tlsConfig` 用 caFile/certFile/keyFile 指向
  `/etc/prometheus/secrets/kube-etcd-client-certs/`，`insecureSkipVerify: true`
  （内网 IP 直连跳过主机名校验，CA 链仍校验）；
  relabelings：`instance` 重写为节点 IP、新增 `node` 标签、**`job` 固定为 `kube-etcd`**
  （对齐 Grafana 看板 `job=~".*etcd.*"` 的匹配与 `cluster` 变量）。

### 3. Prometheus 挂 Secret —— 已固化进 values（不走 kubectl patch 兜底）

`/data1/ssdxt/values/prometheus-stack-values.yaml`（备份 `.bak.0930-etcd`）：

```yaml
prometheus:
  prometheusSpec:
    secrets:
    - kube-etcd-client-certs
```

```bash
helm upgrade prometheus-stack /data1/ssdxt/charts/kube-prometheus-stack-62.7.0.tgz \
  -n monitoring --reuse-values -f /data1/ssdxt/values/prometheus-stack-values.yaml --timeout 15m
```

升级后 `prometheus.spec.secrets=["kube-etcd-client-certs"]`，Prometheus pod 滚动重启、
证书落盘 `/etc/prometheus/secrets/kube-etcd-client-certs/`（已验证）。
`04-etcd-monitoring.sh` 内置检查：secrets 字段缺失时 kubectl patch 兜底并等 Ready——
但**规范做法是 values 固化**，patch 只是保险丝。

### 4. helm upgrade 后军规 7（已执行）

重跑 `02-remote-write.sh`（remoteWrite+queueConfig 已恢复，日志 "Done replaying WAL" 无错误）
与 `03-prometheus-adapter.sh`（pod 重建后 `v1beta1.custom.metrics.k8s.io` Available=True，
`kubectl get --raw` 返回 resources）。

## 三、验证数据（2026-09-30 实测）

`up{job="kube-etcd"}` **= 3 台全 1**（instance=10.100.10.10/.14/.19，node 标签同）。
`etcd_disk_wal_fsync_duration_seconds_count` 每台 2.3 万+ 次连续累计。

**WAL fsync p99（换盘后）**——`histogram_quantile(0.99, sum(rate(..._bucket[5m])) by (instance,le))`：

| 节点 | fsync p99 |
|---|---|
| 10.100.10.10 | **7.1 ms** |
| 10.100.10.14 | **7.9 ms** |
| 10.100.10.19 | **5.0 ms**（首轮 6.8，稳态 ~5） |

对照：旧盘 fio p99 fsync 24~27ms、p99.9 616ms~2.1s（见 40-存储 §1）——**监控数据与换盘验收结论互相印证**（尾延迟改善一个量级，≤10ms 达标）。backend commit p99 另测得 13~15ms，同样健康。

## 四、Grafana 看板核对结果

看板：`Kubernetes / etcd`（ConfigMap `prometheus-stack-kube-prom-etcd`，键 `etcd.json`）。
变量 `cluster` 是隐藏查询变量（`label_values(etcd_server_has_leader{job=~".*etcd.*"}, job)`），
数据进来后自动解析为 `kube-etcd`，面板查询 `job=~".*etcd.*", job="$cluster"` 全部可命中，
**无需改看板**。核心面板查询逐条实测（series 数 / 值）：

| 面板 | 查询 | 结果 |
|---|---|---|
| Up | up{job=~".*etcd.*"} | 3 series 全 1 ✅ |
| has_leader | etcd_server_has_leader | 3 series 全 1 ✅ |
| WAL fsync p99 | histogram_quantile(...fsync...) | 3 series 5~8ms ✅ |
| DB size | etcd_mvcc_db_total_size_in_bytes | 3 series ~47-50MB ✅ |
| RPC rate | rate(grpc_server_started_total) | 有数据 ~22.8/s ✅ |
| Proposals | etcd_server_proposals_committed_total | 3 series ~243万 ✅ |
| Backend commit p99 | histogram_quantile(...backend_commit...) | 3 series 13~15ms ✅ |

验收标准"面板出数"达成。（Grafana admin basic-auth 登录被拒——密码曾被界面修改，
与本次改动无关；核对通过 Prometheus API 模拟面板查询 + dashboard JSON 逐条比对完成。）

## 五、回滚

```bash
kubectl -n monitoring delete servicemonitor,service,endpoints etcd-monitor
kubectl -n monitoring delete secret kube-etcd-client-certs
# values 里删掉 secrets 两行后 helm upgrade --reuse-values -f（随后重跑 02/03，军规 7）
```

不动 etcd、不碰 chart 自带 Service/SM，回滚零风险。

## 六、备注

- remote_write 的 keep 正则本就含 `etcd`，etcd 指标会随 remote_write 推往 plant01
  （注意：`.*_bucket` 被 drop 省带宽，plant01 侧 histogram p99 需本地重算或直查本集群）。
- Endpoints 用了 v1 Endpoints（1.37 提示 deprecated，功能正常）；未来可换 EndpointSlice。
- chart 自带失效的 `prometheus-stack-kube-prom-kube-etcd` Service/SM 保留原样（helm 管理，
  删了会被 upgrade 还原，留着无害）。
