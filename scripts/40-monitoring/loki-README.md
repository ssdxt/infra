# Loki 日志系统使用手册

> 部署位置：`logging` 命名空间 ｜ 采集端：Alloy（11 个 DaemonSet）｜ 查询端：Grafana Explore
> 数据存储：**Longhorn 共享存储**（详见「四、存储」）

---

## 一、快速上手（30 秒）

1. 浏览器打开 **http://10.100.10.10:32298**
2. 登录：`admin` / `<GRAFANA_PASSWORD>`
3. 左侧 **Explore**（指南针图标）→ 顶部数据源选 **Loki**
4. 查询框粘贴，例如：
   ```logql
   {namespace="kube-system"} |= "error"
   ```
5. **右上角时间范围拉到"最近 24 小时"**（默认只有 1 小时，最容易以为"查不到"）

---

## 二、能按什么筛选（标签体系）

```
namespace     命名空间
pod           Pod 名（支持 =~ 正则）
container     容器名
node          节点名（wxq-control-01 … wxq-run-08）
stream        stdout / stderr
job           固定为 pods
service_name  容器名（同上）
filename      日志文件完整路径
```

**语法要点**：
- `{...}` 是**流选择器**，必须放最前面、至少写一个标签
- 后面接**管道过滤器**做内容搜索：`|=` 包含、`!=` 排除、`|~` 正则、`!~` 正则排除
- 多个过滤器串联 = 逻辑与

---

## 三、LogQL 速查（按场景）

### 基础
```logql
{namespace="kube-system"}                                  # 整个命名空间
{namespace="monitoring", pod=~"prometheus.*"}              # 某类 Pod（正则）
{namespace="longhorn-system", stream="stderr"}             # 只看错误输出
{namespace="kube-system"} |= "error"                       # 含 error
{namespace="kube-system"} |= "error" != "not found"        # 含 error 且不含 not found
{namespace="kube-system"} |~ "fail|timeout|refused"        # 正则匹配
```

### 统计（可做告警）
```logql
sum by (pod) (count_over_time({namespace="kube-system"} |= "error" [5m]))          # 谁报错最多
sum(rate({namespace=~".+"} |= "error" [5m])) by (namespace)                        # 各命名空间错误速率
sum(count_over_time({namespace=~".+"}[5m])) by (namespace)                         # 各命名空间日志量
```

### 对应本集群踩过的坑（拿来就用）
```logql
{namespace="kube-system"} |= "slow fdatasync"                    # etcd 慢盘证据
{namespace="kube-system"} |= "became candidate"                  # etcd leader 反复选举
{namespace="kube-system", pod=~"cilium-operator.*"} |= "leader"  # cilium-operator 失租
{namespace="longhorn-system"} |= "stopped leading"               # Longhorn CSI 失租
{namespace="longhorn-system"} |= "Updating TLS secret"           # webhook 证书抖动（已修，应长期为空）
{namespace="kube-system", pod=~"kube-vip.*"} |= "leadership"     # VIP 闪断
{namespace="monitoring"} |= "error"                              # 监控组件自身
```

---

## 四、存储（回答"现在挂的哪个存储"）

```
PVC        storage-loki-0        50Gi   RWO   StorageClass: longhorn
PV         pvc-c39f2fee-…-24656b       回收策略: Delete
Longhorn卷 50 GiB   副本数: 2   前端: blockdev   状态: attached / healthy
挂载节点   wxq-run-07（Loki Pod 所在节点）
实际占用   约 3.8 GB / 50 GB
保留期     168h（7 天）
快照/备份  无（未配置 backup target）
```

**挂载路径**（节点上）：
```
/dev/longhorn/pvc-c39f2fee-…-24656b
  → /data1/kubelet/pods/<poduid>/volumes/kubernetes.io~csi/pvc-c39f2fee-…/mount
  → 容器内 /var/loki
```
> 说明：Longhorn 提供的是**块设备**（`blockdev` 前端），由 kubelet 挂到 CSI 卷目录，再 bind 进容器。**数据在节点 `/data1/longhorn/` 下的副本文件里**，2 份副本分布在不同 worker。

**查看命令**：
```bash
# PVC / PV
kubectl -n logging get pvc -o wide
kubectl get pv pvc-c39f2fee-b8f9-4175-a0c7-1031ca24656b

# Longhorn 卷（副本、健康、所在节点）
kubectl -n longhorn-system get volumes.longhorn.io
kubectl -n longhorn-system get volumes.longhorn.io pvc-c39f2fee-… -o yaml

# 节点上的实际挂载与占用
ssh root@wxq-run-07的IP 'df -h | grep longhorn'
```

### 想调整时改哪里
| 想做什么 | 怎么改 |
|---|---|
| **延长日志保留**（现在 7 天） | 改 `logging/01-loki.sh` 里 `retention_period: 168h` → 如 `720h`(30天)，重新 helm upgrade |
| **扩大容量**（现在 50Gi） | Longhorn 支持在线扩容：`kubectl -n logging patch pvc storage-loki-0 -p '{"spec":{"resources":{"requests":{"storage":"100Gi"}}}}'` |
| **提高可靠性**（现在 2 副本） | Longhorn UI（`longhorn.wuxing.local:32298`）→ Volume → 改副本数；⚠️ 100Mbps 网络下别设 3 |
| **加备份/快照** | Longhorn → Setting → Backup Target 配 S3/NFS；当前**没有备份**，磁盘坏 = 日志丢 |
| **日志量太大** | ① 缩短保留期 ② 在 Alloy 里加过滤（丢 DEBUG/丢掉某些命名空间） ③ 扩 PVC |

---

## 五、命令行方式（不开 Grafana 也能查）

### 5.1 便捷脚本（推荐）
```bash
# 用法
python3 /data1/ssdxt/logging/logq.py '<LogQL>' [条数] [时间范围]
python3 /data1/ssdxt/logging/logq.py -s '<统计LogQL>' [时间窗]

# 例子
python3 /data1/ssdxt/logging/logq.py '{namespace="kube-system"} |= "error"' 20 24h
python3 /data1/ssdxt/logging/logq.py '{namespace="longhorn-system"}' 10 1h
python3 /data1/ssdxt/logging/logq.py -s 'sum by (pod) (count_over_time({namespace="kube-system"} |= "error" [5m]))' 1h
```

### 5.2 原生 API
```bash
# 查日志
kubectl -n logging exec loki-0 -c loki -- wget -qO- \
 'http://localhost:3100/loki/api/v1/query?query={namespace="kube-system"}|="error"&limit=10'

# 有哪些标签
kubectl -n logging exec loki-0 -c loki -- wget -qO- 'http://localhost:3100/loki/api/v1/labels'

# 各命名空间日志量
kubectl -n logging exec loki-0 -c loki -- wget -qO- \
 'http://localhost:3100/loki/api/v1/query?query=sum(count_over_time({namespace=~".+"}[5m])) by (namespace)'
```

---

## 六、排障（"查不到日志"的 5 个原因）

| 现象 | 原因 | 解决 |
|---|---|---|
| 某时间段查不到 | **保留期 7 天**，更早的被删 | 放宽时间无用于是改 `retention_period` |
| 完全没有结果 | Grafana 时间范围默认只有 **1 小时** | 右上角拉宽到 24h |
| 很老的日志没了 | kubelet 日志轮转（10Mi × 5）覆盖了本地文件 | 无法找回；确保 Alloy 一直运行 |
| 某个 Pod 没日志 | 该 Pod 在别的节点且 Alloy 异常 | `kubectl -n logging get ds alloy` 应 11/11 |
| 采集断了 | Alloy 或 Loki 挂了 | `kubectl -n logging get pods`、`kubectl -n logging logs loki-0 -c loki --tail=50` |

**健康检查三连**：
```bash
kubectl -n logging get pods                      # loki-0 2/2，alloy 11/11
kubectl -n logging get ds alloy                  # READY 11
kubectl -n logging exec loki-0 -c loki -- wget -qO- http://localhost:3100/ready
```

---

## 七、数据流（便于理解为什么这样设计）

```
节点 /var/log/pods/*/*/*.log          ← kubelet 写的容器日志（CRI 格式）
   ↓ Alloy（每节点一个，DaemonSet，读本地文件）
   │   • stage.cri          剥掉 CRI 前缀（"<时间> stdout F "）
   │   • stage.regex        从文件路径解析 namespace/pod/container
   │   • static_labels      NODE_NAME 环境变量 → node 标签
   ↓ 推送到 http://loki.logging.svc.cluster.local:3100
Loki（SingleBinary，50Gi Longhorn 卷，保留 7 天）
   ↓
Grafana Explore 查询 / 可基于 LogQL 做告警
```

> **为什么用文件采集而不是走 apiserver**：早期用 `loki.source.kubernetes` 会为**每个容器**开一条 apiserver 长连接（实测 2632 条），把 apiserver 压垮。改成读本地文件后长连接降到 **0**，且不受 apiserver 故障影响。

---

## 八、相关脚本

| 脚本 | 用途 |
|---|---|
| `01-loki.sh` | 部署/更新 Loki（含保留期配置） |
| `02-alloy.sh` | 部署/更新 Alloy 采集端（含配置校验说明） |
| `03-grafana-loki-datasource.sh` | 把 Loki 注册为 Grafana 数据源（幂等） |
| `logq.py` | 命令行查日志的便捷工具 |
