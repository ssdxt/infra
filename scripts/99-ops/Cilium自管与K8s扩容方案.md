# Cilium 自管与 K8s 扩容方案

> 适用环境：wxq 集群（Kubernetes v1.37.0 + Cilium 1.20.1 + kube-vip + Harbor）
> 部署机：**10.100.10.10（wxq-control-01）**，工作目录 `/data1/kubekey/package-ssdxt`
> 读者对象：负责集群扩容 / Cilium 维护的运维人员
> 版本：v1.0（2026-09-28 整理）

---

## 一、结论先行

1. **Cilium 本来就是 Helm release**（`cilium` / kube-system / chart `cilium-1.20.1`），由 KubeKey 在装集群或**扩容时**用离线包里的 chart 执行 `helm upgrade --install`。
2. 所以 **kk 扩容一定会覆盖你手工做的 Cilium 调整**——本次 add nodes 就把它推到了 revision 3，覆盖了之前的补丁（Cilium 镜像 digest、operator 镜像/命令、kube-vip 定时器三处同时失效）。
3. **推荐做法：继续用 kk 管节点生命周期**（离线环境下它把系统初始化、containerd、二进制分发、join 全包了，价值很大），把 Cilium 的差异**固化成一份 values 文件 + 一条收尾补丁**，每次 kk 操作后跑一次即可（2 条命令）。
4. **不建议改用 kubeadm 扩容**：kubeadm 唯一的优势是"不碰 CNI"，但代价是每台新节点都要手工做 kk 现在帮你做的事（系统参数、containerd、二进制、目录/软链、证书、join），离线环境出错面更大。
5. 可选进阶：让 kk 完全不管 CNI（config 里 `cni.type: other`，**待验证**），Cilium 100% 自管，从此互不干扰。

---

## 二、现状（已在集群实测确认）

### 2.1 集群

| 项 | 值 |
|---|---|
| 节点 | 11 台（3 control-plane + 8 worker），**全部 Ready** |
| Kubernetes | v1.37.0（kubeadm 引导，kk 编排） |
| 容器运行时 | containerd v2.3.4 + runc v1.2.6 |
| CNI | Cilium 1.20.1（kube-proxy replacement = true，tunnel/vxlan） |
| API VIP | 10.100.10.250:6443（kube-vip，ARP 模式） |
| Pod / Service 网段 | 10.233.64.0/18 / 10.233.0.0/18 |
| 镜像仓库 | harbor.wuxing.local（10.100.10.29） |

### 2.2 Cilium 的部署方式

| 项 | 值 |
|---|---|
| Helm release | `cilium`，命名空间 `kube-system`，当前 **revision 3** |
| Chart | `cilium-1.20.1`（离线包内路径见下） |
| Chart 文件 | `/data1/kubekey/package-ssdxt/kubekey/kubekey/cni/cilium/cilium-1.20.1.tgz` |
| 状态 | 集群内 cilium / cilium-envoy DaemonSet 均 **11/11 Ready** |
| Helm 管理标记 | DaemonSet 带 `app.kubernetes.io/managed-by: Helm`、`meta.helm.sh/release-name: cilium` |

### 2.3 Cilium 关键参数（取自 cilium-config / Helm values）

```yaml
kubeProxyReplacement: true
ipam: cluster-pool            # clusterPoolIPv4PodCIDRList: 10.233.64.0/18，maskSize 24
routing-mode: tunnel / vxlan
enable-ipv4: true
enable-ipv6: false
enable-hubble: true           # hubble-listen-address :4244
identity-allocation-mode: crd
enable-l7-proxy: true
gatewayAPI.enabled: true
k8sServiceHost: 10.100.10.250
k8sServicePort: 6443
```

镜像仓库映射（kk 写进 values，全部指向 Harbor）：
`image`→`cilium/cilium`、`operator.image`→`cilium/operator`、`envoy.image`→`cilium/cilium-envoy`、
`preflight`→`cilium/cilium`、`nodeinit`→`cilium/startup-script`、`certgen`→`cilium/certgen`、
`clustermesh.apiserver`→`cilium/clustermesh-apiserver`、`hubble.*`→`cilium/hubble-*`、
`spire`→`spiffe/*`、`ztunnel`→`istio/ztunnel`。

### 2.4 kube-vip

- 三个 control 各一个静态 Pod：`/etc/kubernetes/manifests/kube-vip.yaml`
- 当前定时器已去重（`vip_leaseduration` 等只出现 1 次）

---

## 三、根因：kk 扩容为什么会覆盖、为什么会拉不到镜像

`kk add nodes` 的 playbook 里包含 **CNI 角色**，会用离线包的 chart 重新执行 `helm upgrade --install`，于是：

| 现象 | 根因 |
|---|---|
| Cilium 镜像拉取失败 `not found` | chart 默认 `useDigest: true`，渲染出 `repo:tag@sha256:...`。**Harbor 里没有这些摘要**（摘要是上游 Cilium 官方清单的），containerd 按摘要拉必然失败 |
| operator 拉不到 `cilium/operator-generic` | chart 渲染规则是 `repository + "-" + cloud(默认generic) + suffix + tag + digest` → 拼成 `cilium/operator-generic`，**而 Harbor 里的仓库名是 `cilium/operator`**（推送时就是这么命名的） |
| kube-vip 反复重启、VIP 抖动 | kk 重新渲染 control 节点的静态 Pod 清单，模板里同时有硬编码 `5/3/1` 和 kk 自己的 `30/20/5` 两套定时器 → 重复 → 选主抖动 |
| 手工 `kubectl patch` 失效 | patch 改的是 kk/Helm 拥有的对象；下次 `helm upgrade`/apply 时模板里有 image、command、env 字段，一律被覆盖 |

**结论：只要 Cilium 归 kk 管，任何手工调整都是"热补丁"，不持久。**

---

## 四、方案 A（推荐）：values 固化 + 一条收尾补丁

### 4.1 原理

chart 的每个镜像块都支持 **`override`** 字段（原生能力）：**一旦设置就整串原样使用**，不再拼 cloud 后缀、不再加 digest。这是把"去 digest + 改仓库名"固化到声明式配置里的正路。

> 注意：`operator` 的 **command 是模板硬编码** 的 `cilium-operator-<cloud>`（默认 `cilium-operator-generic`），**不随 override 联动**，所以那一条仍需 patch 收尾。当前集群跑的就是 `image=cilium/operator:v1.20.1` + `command=cilium-operator`（已验证可用）。

### 4.2 values 固化文件

在部署机新建 `/data1/kubekey/package-ssdxt/cilium-override.yaml`：

```yaml
# Cilium 镜像去 digest + operator 仓库名修正（覆盖 kk 默认 values 的差异部分）
image:
  override: harbor.wuxing.local/cilium/cilium:v1.20.1

operator:
  image:
    override: harbor.wuxing.local/cilium/operator:v1.20.1

envoy:
  image:
    override: harbor.wuxing.local/cilium/cilium-envoy:v1.37.5-1786810558-766ccfb37260a43e9d228837aa84ce3faf9f64e7

preflight:
  image:
    override: harbor.wuxing.local/cilium/cilium:v1.20.1
  envoy:
    image:
      override: harbor.wuxing.local/cilium/cilium-envoy:v1.37.5-1786810558-766ccfb37260a43e9d228837aa84ce3faf9f64e7
```

**如果还启用了 hubble-relay / hubble-ui / certgen / clustermesh-apiserver 等组件**，用这条命令把渲染结果里所有带摘要的镜像找出来，逐个补 `override`：

```bash
helm get manifest cilium -n kube-system | grep '@sha256' | sort -u
```

### 4.3 应用（两条命令）

```bash
cd /data1/kubekey/package-ssdxt
export KUBECONFIG=/etc/kubernetes/admin.conf

# 1) 用 override 重新渲染 Cilium（保留 kk 原 values，二者叠加）
helm upgrade cilium kubekey/kubekey/cni/cilium/cilium-1.20.1.tgz \
  -n kube-system --reuse-values -f cilium-override.yaml

# 2) 收尾：operator 的 command 修正（模板硬编码，必须补这一刀）
kubectl patch deploy cilium-operator -n kube-system --type strategic \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"cilium-operator","command":["cilium-operator"]}]}}}}'
```

> `--reuse-values` 会沿用 release 里已有的 values（含 kk 写的仓库映射），再叠加 override，避免把仓库地址改回 quay.io。

### 4.4 kube-vip 定时器去重（扩容后必做）

重新渲染后 control 的 kube-vip.yaml 会再次出现重复定时器，跑一次去重即可（就是 `deploy.sh` 第 5 步那段，去掉值为 `5/3/1` 的那一组）：

```bash
for ip in 10.100.10.10 10.100.10.14 10.100.10.19; do
  ssh root@$ip "python3 /tmp/dedup-vip.py"   # 脚本内容见 deploy.sh 第 5 步
done
```

---

## 五、方案 B（进阶）：让 kk 不再管 CNI

`config-sample.yaml` 里 `cni.type` 支持的取值是：`calico / cilium / flannel / hybridnet / kubeovn / other`。

- 把 `cni.type` 设为 **`other`**，预期是"CNI 由用户自备、kk 不安装"→ 之后 kk 扩容不会碰 Cilium，你们可以用 Helm 自由升版本/调参数。
- **待验证**：`other` 的实际行为（是否完全跳过 CNI 角色）**尚未在本环境验证**。切换前请：
  1. 备份 release：`helm get values cilium -n kube-system > cilium-values-backup.yaml`
  2. 在测试环境或用单台 worker 试一次 `kk add nodes`
  3. 扩容后确认 `helm list -n kube-system` 里 cilium 的 revision **没有增长**

风险提示：若 kk 在 `other` 模式下仍执行 CNI 相关清理动作，可能影响现有 Cilium，**不要在业务高峰做这个切换**。

---

## 六、以后升级 Cilium 版本的流程

1. **准备镜像**（离线环境的关键）：把新版本的 `cilium`、`operator`、`cilium-envoy`（以及启用的 hubble/certgen 等）推到 Harbor；**operator 一定要推成 `cilium/operator`** 这个仓库名，与 override 一致。
2. **准备 chart**：更新离线包里的 `cilium-<新版本>.tgz`，或单独放置新 chart 文件。
3. **升级**：`helm upgrade cilium <新chart> -n kube-system --reuse-values -f cilium-override.yaml`（override 里的 tag 同步改成新版本）。
4. **收尾**：跑第 4.3 步的 operator command 补丁；检查 kube-vip 定时器。
5. **验证**：见第七节检查清单。

> 如果走方案 B（kk 不管 CNI），第 3 步之后不需要担心 kk 再覆盖。

---

## 七、扩容（add nodes）标准流程与检查清单

### 7.1 正确命令（**必须带 `-a` 离线包**）

```bash
cd /data1/kubekey/package-ssdxt
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY no_proxy NO_PROXY
export KUBECONFIG=/etc/kubernetes/admin.conf

./kk add nodes -a bundle/kubekey-artifact.tgz -i inventory.yaml -c config.yaml
```

> 不带 `-a` 时 kk 会去 docker.io 拉镜像，离线环境必然失败（DNS 超时），这就是本次故障的直接原因。
> 另外 `kubekey/pki/` 目录务必保留，add nodes 需要里面的 `root.crt`。

### 7.2 扩容后检查清单（本次事故的教训，逐项确认）

| # | 检查项 | 命令 | 期望 |
|---|---|---|---|
| 1 | 节点全部 Ready | `kubectl get nodes` | 无 NotReady |
| 2 | Cilium 就绪 | `kubectl get ds -n kube-system cilium cilium-envoy` | 11/11 |
| 3 | 镜像有没有被写回 digest | `helm get manifest cilium -n kube-system \| grep '@sha256'` | 无输出 |
| 4 | operator 镜像与命令 | `kubectl get deploy cilium-operator -n kube-system -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}{.spec.template.spec.containers[0].command}'` | `...cilium/operator:v1.20.1` + `["cilium-operator"]` |
| 5 | kube-vip 定时器 | `grep -c 'name: vip_leaseduration' /etc/kubernetes/manifests/kube-vip.yaml` | 1 |
| 6 | kube-vip Pod 稳定 | `kubectl get pods -n kube-system \| grep kube-vip` | Running、RESTARTS 不持续增长 |

若第 3/4/5 项不符 → 执行第 4.3、4.4 节的收尾修正。

---

## 八、排障速查

| 症状 | 可能原因 | 排查命令 | 解法 |
|---|---|---|---|
| `kk add nodes` 报 `lookup registry-1.docker.io ... i/o timeout` | 漏了 `-a` 离线包 | 看命令行 | 加 `-a bundle/kubekey-artifact.tgz` |
| Pod `ImagePullBackOff`，报 `@sha256:... not found` | 镜像带摘要、Harbor 无该摘要 | `kubectl describe pod -n kube-system <pod>` | 第 4.2/4.3 节 override + helm upgrade |
| operator 拉 `cilium/operator-generic` 失败 | chart 拼了 `-generic` 后缀 | 同上 | override + command 补丁（4.3） |
| 节点 NotReady、cilium 起不来 | 镜像拉不到 / 内核模块 / containerd 存储损坏 | `kubectl describe node <n>`；节点上 `journalctl -u kubelet -n 50` | 见下条 |
| 报 `failed to stat parent: .../snapshots/N/fs: no such file` | 该节点 containerd 存储损坏（删过节点又加回常见） | 节点上 `crictl images`、`crictl ps` | 重置该节点容器存储：停 kubelet+containerd → 删 `/data1/containerd/io.containerd.{content,snapshotter,metadata,runtime}*` → 重启（该节点无业务负载时可直接做，镜像从 Harbor 重拉） |
| VIP 抖动、kubectl 间歇拿不到数据 | kube-vip 定时器重复 | 第 7.2 节第 5 项 | 跑 dedup-vip.py（去重值 5/3/1 那组） |
| `helm list` 里 cilium revision 持续增长 | kk 每次操作都 helm upgrade | `helm history cilium -n kube-system` | 属正常现象；靠第 4 节收尾保证最终状态正确 |

---

## 九、回滚

```bash
# 查看历史
helm history cilium -n kube-system

# 回滚到上一个版本
helm rollback cilium -n kube-system

# 单独回滚 operator 命令（如果只是命令改错）
kubectl patch deploy cilium-operator -n kube-system --type strategic \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"cilium-operator","command":["cilium-operator-generic"]}]}}}}'
```

建议每次动 Cilium 前先留档：`helm get values cilium -n kube-system > cilium-values-$(date +%F).yaml`。

---

## 十、附录

### 10.1 本次事故时间线（2026-09-28）

| 时间 | 事件 |
|---|---|
| 删除节点阶段 | `kk delete nodes wxq-run-08` 成功，节点从集群移除 |
| 15:50 | `kk add nodes`（**未带 -a**）失败：试图从 docker.io 拉 haproxy 等镜像，DNS 超时 |
| 15:56 | 补上 `-a bundle/kubekey-artifact.tgz` 重跑，进入 playbook |
| 16:01–16:05 | 离线包解压、二进制铺设、kubelet/CNI 安装；**16:05 helm 升级 cilium 到 revision 3** |
| 16:07 | playbook 结束：**total 343，failed 0**，run-08 加入集群 |
| 16:07 之后 | 发现 add nodes 副作用：Cilium 镜像带 digest、operator 变 `operator-generic`、kube-vip 定时器重复 → 3 台节点 NotReady |
| 修复 | ① 三台 control 去重 kube-vip 定时器；② operator 镜像/命令修正；③ cilium、cilium-envoy 两个 DaemonSet 镜像去 digest |
| 结果 | 11/11 节点 Ready，cilium 11/11、cilium-envoy 11/11，集群恢复正常 |

### 10.2 已验证 / 待验证

**已验证（本次实测）**
- Cilium 是 Helm release，kk 扩容会 `helm upgrade` 覆盖手工改动
- chart 渲染规则：`repository-cloud-suffix:tag@digest`；`override` 可整串覆盖
- operator command 由模板硬编码，不随 override 联动
- Harbor 中 operator 的仓库名是 `cilium/operator`
- 去 digest + operator 修正 + kube-vip 去重后，集群恢复正常

**待验证**
- `cni.type: other` 是否让 kk 完全跳过 CNI 安装（方案 B 的前提）
- Harbor 的 `cilium/operator` 镜像内是否同时存在 `cilium-operator-generic` 二进制（若存在，operator 的 command 补丁可省）

### 10.3 关键路径速查

| 内容 | 路径 |
|---|---|
| kk 工作目录 | `/data1/kubekey/package-ssdxt` |
| kk 二进制 | `/data1/kubekey/package-ssdxt/kk` |
| 离线包 | `bundle/kubekey-artifact.tgz`（3.5G） |
| Cilium chart | `kubekey/kubekey/cni/cilium/cilium-1.20.1.tgz` |
| 集群 CA（勿删） | `kubekey/pki/root.crt` |
| 集群 kubeconfig | `/etc/kubernetes/admin.conf` |
| 一键部署脚本（含历史补丁） | `deploy.sh` |
| kube-vip 清单位置 | `/etc/kubernetes/manifests/kube-vip.yaml`（3 台 control） |
| containerd 数据目录 | `/data1/containerd`（`/var/lib/containerd` 软链至此） |
| kubelet 数据目录 | `/data1/kubelet`（`/var/lib/kubelet` 软链至此） |
