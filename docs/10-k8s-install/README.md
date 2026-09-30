# 10 — KubeKey 安装本体（K8s v1.37.0 / kk v4.0.7-patched）

> 本章讲"kk 原生装完是什么样、怎么装"。装完之后的系统级修正见 20 章，CNI 迁移见 30 章。
> **黄金法则：任何对静态 Pod 清单 / kube-vip manifest 的手工修正，都会在每次重跑
> `kk create cluster` 时被 kk 重新渲染覆盖 —— 修正必须放在"最后一次 create cluster 之后"做。**

---

## 【原有功能】

### 1. 安装配置样例（config.yaml）

kk v4 的离线部署配置（集群名 wxq；`<占位>` 按实际环境改）：

```yaml
apiVersion: kubekey.kubesphere.io/v1alpha2
kind: Cluster
metadata:
  name: wxq
spec:
  hosts:
  - {name: wxq-control-01, address: 10.100.10.10, internalAddress: 10.100.10.10, user: root, password: "<ROOT_PWD>"}
  - {name: wxq-control-02, address: 10.100.10.14, internalAddress: 10.100.10.14, user: root, password: "<ROOT_PWD>"}
  - {name: wxq-control-03, address: 10.100.10.19, internalAddress: 10.100.10.19, user: root, password: "<ROOT_PWD>"}
  - {name: wxq-run-01, address: 10.100.10.33, internalAddress: 10.100.10.33, user: root, password: "<ROOT_PWD>"}
  - {name: wxq-run-02, address: 10.100.10.34, internalAddress: 10.100.10.34, user: root, password: "<ROOT_PWD>"}
  - {name: wxq-run-03, address: 10.100.10.39, internalAddress: 10.100.10.39, user: root, password: "<ROOT_PWD>"}
  - {name: wxq-run-04, address: 10.100.10.41, internalAddress: 10.100.10.41, user: root, password: "<ROOT_PWD>"}
  - {name: wxq-run-05, address: 10.100.10.44, internalAddress: 10.100.10.44, user: root, password: "<ROOT_PWD>"}
  - {name: wxq-run-06, address: 10.100.10.45, internalAddress: 10.100.10.45, user: root, password: "<ROOT_PWD>"}
  - {name: wxq-run-07, address: 10.100.10.46, internalAddress: 10.100.10.46, user: root, password: "<ROOT_PWD>"}
  - {name: wxq-run-08, address: 10.100.10.47, internalAddress: 10.100.10.47, user: root, password: "<ROOT_PWD>"}
  roleGroups:
    etcd: [wxq-control-01, wxq-control-02, wxq-control-03]
    control-plane: [wxq-control-01, wxq-control-02, wxq-control-03]
    worker: [wxq-run-01, wxq-run-02, wxq-run-03, wxq-run-04, wxq-run-05, wxq-run-06, wxq-run-07, wxq-run-08]
  controlPlaneEndpoint:
    # API VIP：本集群不用 kk 的 haproxy 内置负载均衡，直接指向 kube-vip 的 VIP
    domain: lb.wuxing.local
    address: "10.100.10.250"
    port: "6443"
  kubernetes:
    version: v1.37.0
    clusterName: cluster.local
    containerManager: containerd
  network:
    plugin: cilium
    kubePodsCIDR: 10.233.64.0/18
    kubeServiceCIDR: 10.233.0.0/18
    # kk 会在 kubelet 上配 clusterDNS=169.254.25.10（nodelocaldns），
    # 但**不会**自动部署 nodelocaldns —— 必须后补（见 30-网络 §4）
  kube_vip:
    enable: true
    vip: 10.100.10.250
    # 期望的租约参数（会被 kk 硬编码 5/3/1 覆盖，装完必须去重修正，见 20-系统层 §4）
    env:
      vip_leaseduration: "30"
      vip_renewdeadline: "20"
      vip_retryperiod: "5"
  registry:
    # 离线：镜像走 kk artifact 推到 Harbor；节点已信任 Harbor 自签 CA
    type: harbor
    auths:
      "harbor.wuxing.local":
        username: admin
        password: "<HARBOR_PWD>"
```

> 注意：以上为按本环境现状整理的样例（真实文件在安装机的工作目录）。三处 kk 渲染 bug
> （kube-vip 定时器重复、Cilium 镜像带 digest、operator 命令不配套）是 v4.0.7-patched 的已知
> 行为，全部靠**装后修正**解决，不要试图在 config.yaml 里绕过。

### 2. 安装命令

```bash
# 在 control-01（安装机）上执行
# ① 先清代理变量！kk 会把 shell 里的代理 env 烘进静态 Pod 清单（90-踩坑 §2）
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY no_proxy NO_PROXY
env | grep -i proxy    # 必须为空

# ② 离线制品就位后（kk artifact 已推 Harbor）
./kk create cluster -f config.yaml -a artifact.tar.gz

# ③ 若中断后重跑：先处理 10 台非 control-01 节点的 kubelet 预检死锁（见 20-系统层 §7）
#    然后再执行同样的 create cluster
```

### 3. kk 装完后集群自带什么（重要认知）

| 组件 | 形态 | 位置 | 备注 |
|---|---|---|---|
| etcd 3.7.0 | **systemd 服务** | `/etc/etcd.env` + `/etc/systemd/system/etcd.service`，证书 `/etc/ssl/etcd/ssl/`，数据 `/var/lib/etcd` | **不是静态 Pod** → 这是 50-监控 §4 "etcd 监控 0 端点" 的根因 |
| kube-apiserver / controller-manager / scheduler | 静态 Pod | `/etc/kubernetes/manifests/*.yaml` | kubelet 直接管理 |
| kube-vip | 静态 Pod | `/etc/kubernetes/manifests/kube-vip.yaml`（3 台 control） | 定时器被 kk 硬编码成 5/3/1 且重复渲染，必须去重修正 |
| kube-proxy | **DaemonSet（默认存在）** | kube-system | Cilium KPR 迁移前正常；迁完后删除（30-网络 §1） |
| Cilium | DaemonSet + operator | kube-system | 镜像引用带 `@sha256:` 且 envoy tag 不对，装完先修镜像（30-网络 §1） |
| localpv-provisioner（OpenEBS） | Deployment | kube-system | kk 默认装；已卸载（40-存储 §1 阻塞问题 3） |
| CoreDNS | Deployment | kube-system | 断点续跑死在 CoreDNS 时需手动 `kubectl apply -f /etc/kubernetes/coredns.yaml` |
| kubelet / containerd | systemd 服务 | 各节点 | kubelet clusterDNS 指向 169.254.25.10（nodelocaldns，需后补部署） |

### 4. 安装完成验证

```bash
export KUBECONFIG=/etc/kubernetes/admin.conf
kubectl get nodes                                   # 期望 11 台（KPR 修完前 worker 可能 NotReady，属 30-网络 §1 的镜像问题）
kubectl -n kube-system get pods | grep -E 'etcd|kube-vip|kube-proxy|cilium'
systemctl is-active etcd                            # active
grep -E 'ELECTION|HEARTBEAT' /etc/etcd.env          # 原始值 5000 / 250
ls /etc/kubernetes/manifests/                       # kube-apiserver/kube-controller-manager/kube-scheduler/kube-vip，**没有 etcd.yaml**
curl -k --noproxy '*' https://10.100.10.250:6443/healthz && echo
```

期望输出（关键行）：

```
NAME             STATUS   ROLES                  AGE   VERSION
wxq-control-01   Ready    control-plane,etcd     ...   v1.37.0
...
ETCD_ELECTION_TIMEOUT=5000
ETCD_HEARTBEAT_INTERVAL=250
ok
```

---

## 【后补调整】

安装本体层面的后补共 4 条，均因"kk 每次重跑会覆盖"而必须**最后再做**：

| # | 调整 | 去处 |
|---|---|---|
| 1 | 代理变量清出节点 /etc/environment 与 Pod 清单 | 20-系统层 §6 |
| 2 | kube-vip 定时器去重 + 参数演进 | 20-系统层 §4 |
| 3 | Cilium 三兄弟镜像修正 | 30-网络 §1 |
| 4 | etcd 选举/心跳放宽（慢盘绕行） | 20-系统层 §2 |

断点续跑两个坑（重跑前必读，命令在 20-系统层 §7）：
- 非安装节点的 kubelet "loaded-but-not-active" 预检死锁 → 先清那些节点的 kubelet 单元；
- **绝不能清 control-01 的 kubelet 单元**——kk 靠它识别"已初始化"，清了会重跑 kubeadm init 报
  `Port 6443 is in use`。

---

## 【回滚】

kk 集群整体回滚 = 重建。单组件回滚都在各章内给出。重装前记录当前 config.yaml 与
`kk artifact` 版本，保证可重复。
