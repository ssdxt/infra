# 30-网络与CNI §8 — Cilium 全栈能力（统一 values + WireGuard / BandwidthManager / EgressGateway / BGP）

> 完成日期：2026-09-30。Cilium 1.20.1，helm release revision 10，K8s 1.37，11 节点。
> 前置章节：§1 KPR 迁移、§3 Gateway API、§6 HTTPS 化、§7 Hubble 可观测性。

## 1. 统一 values 理念（唯一事实来源）

- **文件**：control-01 `/data1/ssdxt/values/cilium-values-unified.yaml`（文件头注释即操作铁律）。
- **生成方式**：`helm -n kube-system get values cilium -a -o yaml`（全量生效值，含默认）打底，
  python 精确合并开关，**既有键一律不动**。
- 以后任何 Cilium 变更只改这一个文件 → helm upgrade → 跑回归清单。禁止再用 `--set` 零散打点。
- 备份：`/data1/ssdxt/values/backup/20260930-113945/`（升级前 values、full release、
  ds/deploy/svc/cm 资源、Cilium CR 现状、gateway svc）。

### 关键新增/修正键（本次踩坑沉淀）

| 键 | 值 | 为什么 |
|---|---|---|
| `encryption.enabled/type` | true / wireguard | WireGuard 加密（内核 5.15 自带模块） |
| `bandwidthManager.enabled` | true | 带宽管理（EDT with BPF + fq qdisc） |
| `egressGateway.enabled` | true | Egress 网关开关（策略 CR 另配） |
| `bgpControlPlane.enabled` | true | BGP 控制面开关（peering policy 另配） |
| `enableIPv4Masquerade` / `bpf.masquerade` | true / true | **egressGateway 硬性要求** BPF masquerade，缺了 agent 直接 fatal |
| 全部镜像块 `useDigest: false` | — | chart 默认附加 `@sha256:` 摘要，Harbor 单架构复刻后摘要不存在 → ImagePullBackOff |
| `operator.image.override` | harbor.wuxing.local/cilium/operator:v1.20.1 | chart 按模板拼 `repository-generic`，Harbor 无 `cilium/operator-generic` 仓库 |

### ⚠️ helm upgrade 铁律（本次实测 4 轮踩坑总结）

1. **不要用 `--wait`**：chart 把 operator 命令硬编码渲染为 `cilium-operator-generic`
   （`templates/cilium-operator/deployment.yaml` 第 85 行），Harbor 镜像里没有该二进制，
   operator 必 CrashLoop，`--wait` 一定 15m 超时收场。用 `--timeout 3m` 裸升。
2. 升级后必做 3 个 kubectl 补丁（幂等，详见文件头注释）：
   - operator command → `cilium-operator`
   - hubble-peer svc `internalTrafficPolicy` → `Cluster`
   - 检查 gateway svc nodePort `port-443=32298/port-80=32299`，被重置则按端口名 patch
3. 改完若 agent 未滚动：`kubectl -n kube-system rollout restart ds/cilium ds/cilium-envoy deploy/cilium-operator deploy/hubble-relay`
4. 回滚：`helm upgrade ... -f /data1/ssdxt/values/backup/<ts>/cilium-values-before-unified.yaml` + 重打 3 补丁。

## 2. 四开关详解（本文档落地时的状态与实证）

### 2.1 WireGuard 加密 ✅

- configmap：`enable-wireguard: "true"`；接口 `cilium_wg0`，端口 51871，10 个 peer（11 节点全互联）。
- `cilium-dbg status`：`Encryption: Wireguard [NodeEncryption: Disabled, cilium_wg0 (Pubkey: ..., Peers: 10)]`
- **实证**：wxq-run-01→wxq-run-06 跨节点 Pod ping（30×1024B，0% 丢包），
  wxq-run-06 `cilium_wg0` tx_bytes **2234980 → 2536152（+300KB）**——跨节点 Pod 流量全部进 WG 隧道。
- 注意：NodeEncryption 为 Disabled（默认），Pod-to-Pod 与 Pod-to-Node 已加密；节点host流量不加密。

### 2.2 Bandwidth Manager ✅

- `cilium-dbg status`：`BandwidthManager: EDT with BPF [CUBIC] [ens3]`。
- 节点实证：`tc qdisc show` 出现多条 `qdisc fq ... dev ens3 parent 8002:x`（Cilium 挂的 fq）。
- 用法示例（Pod 限速 10Mbit）：
  ```yaml
  apiVersion: v1
  kind: Pod
  metadata:
    annotations:
      kubernetes.io/egress-bandwidth: "10M"   # 出向限速
      kubernetes.io/ingress-bandwidth: "20M"  # 入向限速
  ```

### 2.3 Egress Gateway ✅（开关已开，策略未配）

- 开关在 `enable-egress-gateway: "true"`；**真正引导流量需要 CiliumEgressGatewayPolicy CR**。
- 示例模板（占位，按需填实后 apply）：
  ```yaml
  apiVersion: cilium.io/v2
  kind: CiliumEgressGatewayPolicy
  metadata:
    name: egress-sample            # 示例名
  spec:
    selectors:
    - podSelector:
        matchLabels:
          app: need-egress         # ← 改：哪些 Pod 走 egress 网关
    destinationCIDRs:
    - "0.0.0.0/0"                  # ← 改：目标网段
    egressGateway:
      nodeSelector:
        matchLabels:
          egress: "true"           # ← 改：承担 egress 的节点标签（提前打）
      # egressIP: 10.100.10.x     # 可选：SNAT 出口 IP（须在节点网卡上可达）
  ```
- 注意：eBPF masquerade 必须开（本环境已开）；egress 节点选择标签要提前规划。

### 2.4 BGP Control Plane ✅（开关已开，peering 未配）

- 开关在 `enable-bgp-control-plane: "true"`；**真正对外广播路由需要 CiliumBGPPeeringPolicy CR
  + 交换机侧 ASN/对端信息**，本环境未配（无 ToR BGP 需求前不动）。
- 示例模板（占位）：
  ```yaml
  apiVersion: cilium.io/v2alpha1
  kind: CiliumBGPPeeringPolicy
  metadata:
    name: bgp-sample
  spec:
    nodeSelector:
      matchLabels:
        bgp: "true"              # ← 改：参与 BGP 的节点标签
    virtualRouters:
    - localASN: 65001            # ← 占位：本侧 ASN
      exportPodCIDR: true       # 广播 Pod CIDR；LB 池用 serviceSelector+bgpPage
      neighbors:
      - peerAddress: "10.100.10.1/32"   # ← 占位：交换机对端地址
        peerASN: 65000                  # ← 占位：对端 ASN
  ```
- 配套还需要：节点打标签、CiliumLoadBalancerIPPool（已有 gateway-pool 可复用）、
  交换机侧 neighbor 配置。Linked feature：`routingMode` 需为 native（当前是 tunnel/vxlan，
  **启用 BGP 广播前要评估切 native routing，属破坏性变更需单独窗口**）。

## 3. 回归清单（每次 helm upgrade 后全跑）

1. `kubectl -n kube-system get ds cilium`：11/11 ready；`cilium-dbg status` 无报错、
   KubeProxyReplacement True、Controller 全 healthy。
2. 4 项镜像修复在位：
   - agent 容器名 `cilium-agent`、镜像 `harbor.wuxing.local/cilium/cilium:v1.20.1`；
   - agent init 容器无 `@sha256:`；
   - operator 命令 `cilium-operator`、镜像 `harbor.wuxing.local/cilium/operator:v1.20.1`；
   - cilium-envoy 镜像长版本 tag。
3. hubble-peer svc `internalTrafficPolicy: Cluster`；hubble-relay 日志 11 节点 Connected、无 error。
4. gateway svc：`port-443=32298`、`port-80=32299`。
5. 6 域名全通（实测 302/200/200/302/200/200）：
   `curl -sk https://{grafana,longhorn,alertmanager,prometheus,argocd,hubble}.wuxing.local:32298/`
6. WireGuard：`cilium-dbg status` 显示 Wireguard + peers=10；跨节点 Pod 流量使
   `cilium_wg0` tx_bytes 增长。
7. 带宽管理：status 显示 `BandwidthManager: EDT with BPF`；节点 `tc qdisc show` 有 `qdisc fq`。
8. etcd：`kubectl get --raw="/readyz?verbose" | grep etcd` 两项 ok；Prometheus kube-etcd 3/3 up。
9. Prometheus targets：cilium-agent-metrics 11/11、cilium-envoy-metrics 11/11、
   cilium-operator-metrics 2/2 全 up；remote_write：`prometheus_remote_storage_samples_failed_total`=0、
   samples/s 持续增长（实测 ~3511/s）。

## 4. Tetragon（下一步可选项，未部署）

- Tetragon 是 **Cilium 家族的独立安全运行时执行 chart**（eBPF 探针做系统调用级追踪/策略执行），
  与 Cilium 网络身份互补：Cilium 管 L3-L7 网络策略，Tetragon 管进程/文件/能力级执行策略与审计。
- **独立 chart、独立镜像**（quay.io/cilium/tetragon 等），部署前必须先搬 Harbor（skopeo amd64，
  禁止 `@sha256:` 摘要引用，显式 tag），军规 3 适用。
- 部署样例（镜像搬完后）：
  ```bash
  helm upgrade --install tetragon /data1/ssdxt/charts/tetragon-<ver>.tgz \
    -n kube-system \
    --set image.repository=harbor.wuxing.local/cilium/tetragon \
    --set image.tag=<tag> \
    --set tetragonOperator.image.repository=harbor.wuxing.local/cilium/tetragon-operator \
    --set tetragonOperator.image.tag=<tag> \
    --set exportPolicyResources.enabled=true
  kubectl -n kube-system get ds tetragon   # 11/11
  tetra tracingpolicy list                  # 策略观察
  ```
- 建议窗口：与 Cilium 大版本升级错开；先 observe-only（TracingPolicy）再上 Enforce（网络与
  进程双管齐下前先在测试 ns 演练）。

## 5. 本次变更证据留档

- helm history：rev 6/7/8 failed（摘要回填与 --wait 超时，见 §1 铁律）→ **rev 9/10 deployed**。
- 升级后全 Pod 健康（cilium 11、cilium-envoy 11、operator 2、hubble-relay/ui 正常）。
- 统一 values 头注释含完整升级五步；备份在 `/data1/ssdxt/values/backup/20260930-113945/`。
