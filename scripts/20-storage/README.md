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
