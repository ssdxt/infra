#!/bin/bash
# ============================================================
# 在 control-01 上建立 /data1/ssdxt 的完整组件目录体系
# 运行: bash bootstrap-dirs.sh
# 说明: 所有脚本都是"看一眼就懂"的形式，方便你自行调整
# ============================================================
set -e
R=/data1/ssdxt
H=harbor.wuxing.local

mkdir -p $R/{images,tools,storage,monitoring,logging,gateway}

# ============ 1. 总纲 README ============
cat > $R/README.md <<'EOF'
# wxq 集群交付目录说明（/data1/ssdxt）

> 所有可复现的安装材料、脚本、文档都在这里。每个子目录都有一份 README.md 说明"怎么装、怎么改、怎么验"。

## 目录导航

| 目录 | 内容 | 关键脚本 |
|---|---|---|
| `charts/` | 所有 helm 图表包（cilium / cert-manager / kube-prometheus-stack / gateway-api / nodelocaldns） | — |
| `values/` | 已部署组件的 values 快照（回滚/复刻用） | — |
| `tools/` | 通用工具 | `fix-chart-images.py`（自动把图表镜像改写为 Harbor） |
| `images/` | 镜像搬运 | `mirror.sh`（skopeo 批量搬 amd64 镜像到 Harbor） |
| `storage/` | 共享存储（NFS + Longhorn） | `01-nfs-server-plant02.sh`、`02-nfs-client-nodes.sh`、`03-longhorn-install.sh` |
| `monitoring/` | 监控增强 | `01-metrics-server.sh`、`02-remote-write.sh` |
| `logging/` | 日志体系（Loki + Alloy） | `01-loki.sh`、`02-alloy.sh` |
| `gateway/` | Gateway API 对外暴露（持久化） | `01-deploy.sh` |

## 当前集群已部署的组件（2026-09-29）

| 组件 | 命名空间 | 访问方式 |
|---|---|---|
| Cilium 1.20.1（KPR 模式） | kube-system | — |
| cert-manager 1.16.1 | cert-manager | — |
| kube-prometheus-stack 62.7.0 | monitoring | Grafana `admin/<GRAFANA_PASSWORD>` |
| nodelocaldns | kube-system | — |
| Gateway API（GatewayClass: cilium） | — | 待建 Gateway |

## Harbor 账号
- 地址 `harbor.wuxing.local`（10.100.10.29）
- 账号 `admin` / `<HARBOR_PASSWORD>`
- CA 证书：`/etc/docker/certs.d/harbor.wuxing.local/ca.crt`（各节点已信任）

## 重要约定（调整时请遵守）

1. **镜像全部走 Harbor**，绝不依赖外网（要新镜像用 `images/mirror.sh` 搬）
2. **chart 的镜像路径用 `tools/fix-chart-images.py` 自动改写**，不要手工猜 values 路径
   ```bash
   python3 tools/fix-chart-images.py <chart.tgz> <项目名> harbor.wuxing.local /tmp/out.yaml
   ```
3. **helm upgrade cilium 后必须重跑镜像修正**（见 `集群改造详细命令记录.md` 第二章）
4. **暴露服务用 Gateway，不要用 nohup 端口转发**
EOF

# ============ 2. storage/README.md ============
cat > $R/storage/README.md <<'EOF'
# 共享存储方案（两条路，可并存）

| | NFS（plant02 单机） | Longhorn（分布式） |
|---|---|---|
| 原理 | 一台 NFS 服务器共享目录 | 用每台节点的 /data1，2~3 副本 |
| 容灾 | ❌ 单点 | ✅ 节点掉线数据还在 |
| RWX | ✅ 原生 | ✅ share-manager |
| 快照/备份 | ❌ | ✅ 内置 |
| 开销 | 几乎为零 | 每节点 2-3 CPU / 2G 内存 |
| 100Mbps 网络 | 读写受百兆限制 | ⚠️ 写多副本放大网络流量 |

**建议**：Longhorn 做默认 StorageClass（有 HA），NFS 用于"大容量、不需副本"的场景（日志、备份落地）。

## 怎么用

```bash
# 看有哪些 StorageClass
kubectl get sc

# 用 Longhorn 起一个 PVC
cat <<'YAML' | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: demo-pvc
spec:
  accessModes: ["ReadWriteOnce"]
  storageClassName: longhorn
  resources:
    requests:
      storage: 5Gi
YAML

# 用 NFS（静态 PV，需先建）
kubectl get pv
```

## 调整点

| 想改什么 | 改哪里 |
|---|---|
| Longhorn 副本数 | `03-longhorn-install.sh` 里 `defaultReplicaCount`（默认 2，网络慢别设 3） |
| Longhorn 用哪块盘 | `03-longhorn-install.sh` 里 `defaultDataPath`（当前 `/data1/longhorn`） |
| NFS 导出目录/权限 | plant02 上 `/etc/exports` |
| 默认 StorageClass | `kubectl patch storageclass <名> -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'` |
EOF

# ============ 3. NFS 服务器脚本（plant02）============
cat > $R/storage/01-nfs-server-plant02.sh <<'EOF'
#!/bin/bash
# 在 plant02 (10.100.10.31) 上部署 NFS 服务器（已执行过，重复运行安全）
NFS_DIR=/data1/k8s-nfs
CLIENT_NET=10.100.10.0/24
apt-get install -y -qq nfs-kernel-server
mkdir -p $NFS_DIR && chmod 0777 $NFS_DIR
grep -q "$NFS_DIR" /etc/exports || echo "$NFS_DIR $CLIENT_NET(rw,sync,no_subtree_check,no_root_squash)" >> /etc/exports
exportfs -ra
systemctl enable --now nfs-server
echo "NFS 就绪: 10.100.10.31:$NFS_DIR"
exportfs -v
EOF

# ============ 4. NFS 客户端脚本（11 节点）============
cat > $R/storage/02-nfs-client-nodes.sh <<'EOF'
#!/bin/bash
# 给 11 台集群节点装 NFS 客户端（已执行过）
NODES="10.100.10.10 10.100.10.14 10.100.10.19 10.100.10.33 10.100.10.34 10.100.10.39 10.100.10.41 10.100.10.44 10.100.10.45 10.100.10.46 10.100.10.47"
for ip in $NODES; do
  ssh -o BatchMode=yes root@$ip 'dpkg -l | grep -q "^ii  nfs-common" || { apt-get update -qq; apt-get install -y -qq nfs-common; }; command -v mount.nfs' | sed "s/^/  $ip: /"
done
echo "验证: showmount -e 10.100.10.31"
EOF

# ============ 5. Longhorn 安装脚本 ============
cat > $R/storage/03-longhorn-install.sh <<'EOF'
#!/bin/bash
# 安装 Longhorn（用节点 /data1 做分布式存储，2 副本）
# 前提: 镜像已用 images/mirror.sh 搬完、节点已装 open-iscsi
set -e
export KUBECONFIG=/etc/kubernetes/admin.conf
R=/data1/ssdxt
H=harbor.wuxing.local
CHART=$R/charts/longhorn-1.7.2.tgz
NS=longhorn-system

echo "=== [1/4] 节点前置：open-iscsi（Longhorn 用 iSCSI 提供块设备）==="
for ip in 10.100.10.10 10.100.10.14 10.100.10.19 10.100.10.33 10.100.10.34 10.100.10.39 10.100.10.41 10.100.10.44 10.100.10.45 10.100.10.46 10.100.10.47; do
  ssh -o BatchMode=yes root@$ip 'dpkg -l | grep -q "^ii  open-iscsi" || { apt-get update -qq; apt-get install -y -qq open-iscsi; }; systemctl enable --now iscsid >/dev/null 2>&1; echo ok' >/dev/null 2>&1 &
done
wait
echo "  完成"

echo "=== [2/4] 自动改写镜像为 Harbor ==="
python3 $R/tools/fix-chart-images.py $CHART longhorn $H /tmp/longhorn-values.yaml

echo "=== [3/4] 写自定义参数 ==="
cat > /tmp/longhorn-custom.yaml <<YAML
defaultSettings:
  defaultReplicaCount: 2
  defaultDataPath: /data1/longhorn
  # 100Mbps 网络下降低重建压力
  concurrentReplicaRebuildPerNodeLimit: 1
persistence:
  defaultClass: true
  defaultClassReplicaCount: 2
YAML

echo "=== [4/4] helm 安装 ==="
helm upgrade --install longhorn $CHART -n $NS --create-namespace \
  -f /tmp/longhorn-values.yaml -f /tmp/longhorn-custom.yaml --timeout 15m 2>&1 | tail -5

echo ""
echo "=== 验证（等 2~3 分钟）==="
echo "  kubectl -n longhorn-system get pods"
echo "  kubectl get sc              # 应出现 longhorn (default)"
echo "  kubectl -n longhorn-system get svc longhorn-frontend   # UI"
echo ""
echo "=== Longhorn UI 访问（用 Gateway 或端口转发）==="
echo "  kubectl -n longhorn-system port-forward svc/longhorn-frontend 8080:80"
EOF

# ============ 6. monitoring/README.md ============
cat > $R/monitoring/README.md <<'EOF'
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
EOF

# ============ 7. metrics-server 脚本 ============
cat > $R/monitoring/01-metrics-server.sh <<'EOF'
#!/bin/bash
# 安装 metrics-server（让 kubectl top / HPA 可用）
# 说明: metrics-server 提供 metrics.k8s.io API，prometheus-stack 不提供这个
set -e
export KUBECONFIG=/etc/kubernetes/admin.conf
H=harbor.wuxing.local
IMG=$H/metrics-server/metrics-server:v0.7.2

cat <<YAML | kubectl apply -f -
apiVersion: v1
kind: ServiceAccount
metadata: {name: metrics-server, namespace: kube-system}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata: {name: system:metrics-server}
rules:
- apiGroups: [""]
  resources: [nodes/metrics, nodes/stats, pods, nodes]
  verbs: [get, list, watch]
- apiGroups: [""]
  resources: [pods/stats]
  verbs: [get]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata: {name: system:metrics-server}
roleRef: {apiGroup: rbac.authorization.k8s.io, kind: ClusterRole, name: system:metrics-server}
subjects: [{kind: ServiceAccount, name: metrics-server, namespace: kube-system}]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata: {name: metrics-server-auth-reader, namespace: kube-system}
roleRef: {apiGroup: rbac.authorization.k8s.io, kind: Role, name: extension-apiserver-authentication-reader}
subjects: [{kind: ServiceAccount, name: metrics-server, namespace: kube-system}]
---
apiVersion: apiregistration.k8s.io/v1
kind: APIService
metadata:
  name: v1beta1.metrics.k8s.io
spec:
  service: {name: metrics-server, namespace: kube-system}
  group: metrics.k8s.io
  version: v1beta1
  insecureSkipTLSVerify: true
  groupPriorityMinimum: 100
  versionPriority: 100
---
apiVersion: apps/v1
kind: Deployment
metadata: {name: metrics-server, namespace: kube-system, labels: {k8s-app: metrics-server}}
spec:
  replicas: 1
  selector: {matchLabels: {k8s-app: metrics-server}}
  template:
    metadata: {labels: {k8s-app: metrics-server}}
    spec:
      serviceAccountName: metrics-server
      priorityClassName: system-cluster-critical
      nodeSelector: {kubernetes.io/os: linux}
      containers:
      - name: metrics-server
        image: $IMG
        args:
        - --cert-dir=/tmp
        - --secure-port=10250
        - --kubelet-preferred-address-types=InternalIP
        - --kubelet-use-node-status-port
        - --metric-resolution=30s
        # 关键: kubelet 是自签证书，必须跳过校验
        - --kubelet-insecure-tls
        ports:
        - {name: https, containerPort: 10250, protocol: TCP}
        livenessProbe:
          httpGet: {path: /livez, port: https, scheme: HTTPS}
          initialDelaySeconds: 20
        readinessProbe:
          httpGet: {path: /readyz, port: https, scheme: HTTPS}
          initialDelaySeconds: 20
---
apiVersion: v1
kind: Service
metadata: {name: metrics-server, namespace: kube-system, labels: {k8s-app: metrics-server}}
spec:
  selector: {k8s-app: metrics-server}
  ports: [{name: https, port: 443, targetPort: https}]
YAML

echo "等 30 秒后验证:"
echo "  kubectl top nodes"
echo "  kubectl top pods -A | head"
EOF

# ============ 8. remote-write 脚本 ============
cat > $R/monitoring/02-remote-write.sh <<'EOF'
#!/bin/bash
# 把本集群 Prometheus 数据推送到 plant01（10.100.10.29:9091）
# 前置: plant01 Prometheus 需带 --web.enable-remote-write-receiver 参数重启
set -e
export KUBECONFIG=/etc/kubernetes/admin.conf
PLANT01=10.100.10.29:9091

echo "=== [1/2] 检查 plant01 接收端是否就绪 ==="
if curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://$PLANT01/api/v1/status/runtimeinfo" | grep -q 200; then
  echo "  plant01 Prometheus 可达"
else
  echo "  !! plant01 Prometheus 不可达，检查地址/网络"
fi
echo "  提示: 若推送报 404，需要在 plant01 上加启动参数 --web.enable-remote-write-receiver 并重启容器"

echo ""
echo "=== [2/2] 给本集群 Prometheus 加 remoteWrite ==="
cat > /tmp/remote-write-patch.yaml <<YAML
spec:
  remoteWrite:
  - url: http://$PLANT01/api/v1/write
    remoteTimeout: 60s
    writeRelabelConfigs:
    - action: keep
      regex: (kubelet|node-exporter|kube-state-metrics|apiserver|etcd|kube-scheduler|kube-controller-manager|coredns|prometheus)
      sourceLabels: [job]
YAML
kubectl -n monitoring patch prometheus prometheus-stack-kube-prom-prometheus \
  --type merge --patch-file /tmp/remote-write-patch.yaml

echo "  已写入。验证（1~2 分钟后）:"
echo "    在 plant01 Grafana 查询 up{cluster=\"wxq\"} 或看 job 列表"
echo "    本集群检查: kubectl -n monitoring logs prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus | grep -i remotewrite"
EOF

echo "=== 目录已建立 ==="
find $R -maxdepth 2 -type f -name '*.sh' -o -maxdepth 2 -type f -name '*.md' -o -maxdepth 2 -type f -name '*.py' | sort
