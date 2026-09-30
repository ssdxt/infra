# 监控使用说明

## 1. 登录 Grafana

```
用户名 admin
密码   <GRAFANA_PASSWORD>          # kube-prometheus-stack 默认
```
密码查询：
```bash
kubectl get secret prometheus-stack-grafana -n monitoring -o jsonpath='{.data.admin-password}' | base64 -d; echo
```

## 2. 访问方式（三选一）

| 方式 | 命令 | 特点 |
|---|---|---|
| **Gateway 域名**（推荐） | 见 `../gateway/README.md` | ✅ 持久化，浏览器直连域名 |
| 端口转发 | `kubectl port-forward -n monitoring svc/prometheus-stack-grafana 3000:80 --address 0.0.0.0` | ⚠️ 临时，SSH 断了就断 |
| NodePort | 改 Grafana Service type | 一般 |

## 3. 关键数据怎么抓（PromQL 速查）

### 节点掉线检测
```promql
# 哪些节点掉线了（node-exporter 抓不到 = 节点/网络有问题）
up{job="prometheus-stack-prometheus-node-exporter"} == 0

# 节点 Ready 状态（0 = 未就绪）
kube_node_status_condition{condition="Ready",status="true"} == 0

# kubelet 是否失联
up{job="kubelet"} == 0

# 现成的告警规则（已在跑，共 230 条）
#   KubeNodeNotReady / KubeletDown / TargetDown / NodeNetworkInterfaceFlapping
```

### 容器资源使用（不需要 metrics-server）
```promql
# 每个容器的 CPU 使用（核）
sum by (namespace,pod,container) (rate(container_cpu_usage_seconds_total{container!=""}[5m]))

# 每个容器的内存（工作集）
sum by (namespace,pod,container) (container_memory_working_set_bytes{container!=""})

# 容器重启次数 Top10
topk(10, kube_pod_container_status_restarts_total)

# OOM 被杀过的容器
kube_pod_container_status_last_terminated_reason{reason="OOMKilled"}
```

### 存储/etcd 健康（之前的痛点）
```promql
# etcd WAL fsync 延迟 p99（>10ms 说明盘慢）
histogram_quantile(0.99, rate(etcd_disk_wal_fsync_duration_seconds_bucket[5m]))

# etcd leader 变更次数（>0 说明存储抖动）
increase(etcd_server_leader_changes_seen_total[1h])

# 节点磁盘使用率
(1 - node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"} / node_filesystem_size_bytes{fstype!~"tmpfs|overlay"}) * 100
```

## 4. 推荐看板（Grafana → Dashboards，共 27 个）
| 看板 | 用途 |
|---|---|
| `k8s-resources-cluster` | 集群总览 |
| `k8s-resources-node` | 节点明细 |
| `k8s-resources-pod` | **单容器资源**（你问的） |
| `etcd` / `apiserver` | 控制面健康（存储问题看这里） |
| `k8s-coredns` | DNS |

## 5. 告警怎么配（两种，选一）

**方案 A（推荐）：交给 plant01 统一告警**
```bash
bash 03-alerting-to-plant01.sh     # 把 230 条规则同步到 plant01，复用它的飞书渠道
```
**方案 B：本集群自己发**
给本集群 Alertmanager 配接收器，webhook 可指向 plant01 的 `http://10.100.10.29:8280`

## 6. 数据保留与持久化
- 默认 `retention: 10d` + **emptyDir（Pod 重启历史全丢）**
- 有共享存储后挂 PVC：`bash 02-prometheus-pvc.sh`
- 或推送到 plant01 做长期存储：`bash 02-remote-write.sh`
