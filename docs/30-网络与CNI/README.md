# 30 — 网络与 CNI（Cilium KPR / kube-vip / Gateway API / nodelocaldns / 已知问题）

> 目标态：**Cilium 1.20.1 全量接管 kube-proxy 功能（KPR=true）+ Gateway API 对外暴露 + nodelocaldns 本地 DNS 缓存**。
> 资产：`/data1/ssdxt/charts/cilium-1.20.1.tgz`、`values/cilium-values.yaml`、
> `charts/gateway-api/experimental-install.yaml`、`charts/nodelocaldns.yaml`、`gateway/01-deploy.sh`。

---

## §1 Cilium KubeProxyReplacement（KPR）迁移

**【原有功能】** kk 用 cilium chart 装 Cilium，但默认 `kubeProxyReplacement=false`，
kube-proxy DaemonSet（nftables 模式）负责 Service 转发。本环境 kube-proxy 的 nft 规则从未编程成功
（`nft list ruleset | grep -c kube` = 0），ClusterIP 全断。

**【后补调整】**

- **为什么删 kube-proxy**：① kube-proxy 规则失效导致 ClusterIP/DNS 不通；② Gateway API 是
  Cilium 1.20 的硬性前提——operator 日志实锤：
  `level=warn msg="Gateway API support requires kube-proxy-replacement enabled"`；
  ③ KPR 由 Cilium 在内核 eBPF 层直做 Service/NAT，少一层 iptables/nftables 同步。
- **迁移前先备份 values（必做，否则丢 kk 的配置）**：
  ```bash
  export KUBECONFIG=/etc/kubernetes/admin.conf
  helm get values cilium -n kube-system -o yaml > /data1/ssdxt/cilium-values-before-kpr.yaml
  ```
- **helm upgrade 开启 KPR + Gateway API**：
  ```bash
  helm upgrade cilium /data1/ssdxt/charts/cilium-1.20.1.tgz -n kube-system \
    -f /data1/ssdxt/cilium-values-before-kpr.yaml \
    --set kubeProxyReplacement=true \
    --set k8sServiceHost=10.100.10.250 \
    --set k8sServicePort=6443 \
    --set gatewayAPI.enabled=true \
    --timeout 15m
  ```
- **关键坑：Cilium ConfigMap 没有 checksum 注解** → 改完 `cilium-config` **不会自动滚动**，必须手动：
  ```bash
  kubectl -n kube-system rollout restart ds/cilium
  kubectl -n kube-system rollout restart deploy/cilium-operator
  kubectl -n kube-system rollout status ds/cilium --timeout=480s
  ```
- **4 个镜像修复**（helm upgrade 会把镜像引用重置回 chart 默认，**每次 upgrade 后都要重做一遍**）：
  1. agent 主容器**容器名是 `cilium-agent`**（不是 `cilium`）：
     ```bash
     kubectl -n kube-system set image ds/cilium cilium-agent=harbor.wuxing.local/cilium/cilium:v1.20.1
     ```
  2. agent 的 init 容器（config/mount-cgroup/apply-sysctl-overwrites/mount-bpf-fs/
     clean-cilium-state/install-cni-binaries）全部带 `@sha256:`，用 python 通用去 digest：
     ```bash
     kubectl -n kube-system get ds cilium -o json | python3 -c "
     import json,sys,subprocess
     d=json.load(sys.stdin)
     spec=d['spec']['template']['spec']; body={}
     for ck in ('initContainers','containers'):
         nl=[{'name':c['name'],'image':c['image'].split('@sha256:')[0]}
             for c in spec.get(ck) or [] if '@sha256:' in c.get('image','')]
         if nl: body[ck]=nl
     p=json.dumps({'spec':{'template':{'spec':body}}})
     subprocess.run(['kubectl','patch','ds','cilium','-n','kube-system','--type','strategic','-p',p])
     print('patched')"
     ```
  3. operator：镜像换成 `harbor.wuxing.local/cilium/operator:v1.20.1` 且**命令里的二进制名
     `cilium-operator-generic` 要改回 `cilium-operator`**（kk 推的镜像里没有 -generic 这个二进制，
     报 `exec: "cilium-operator-generic": executable file not found`）：
     ```bash
     kubectl -n kube-system set image deploy/cilium-operator \
       cilium-operator=harbor.wuxing.local/cilium/operator:v1.20.1
     kubectl -n kube-system patch deploy cilium-operator --type json \
       -p '[{"op":"replace","path":"/spec/template/spec/containers/0/command/0","value":"cilium-operator"}]'
     ```
  4. envoy：chart 默认 tag `v1.20.1`，Harbor 里实际是长版本串：
     ```bash
     curl -sk -u admin:'<HARBOR_PASSWORD>' 'https://harbor.wuxing.local/v2/cilium/cilium-envoy/tags/list'
     kubectl -n kube-system set image ds/cilium-envoy \
       cilium-envoy=harbor.wuxing.local/cilium/cilium-envoy:v1.37.5-1786810558-766ccfb37260a43e9d228837aa84ce3faf9f64e7
     ```
- **删除 kube-proxy（完成 kube-proxy-free）**：
  ```bash
  kubectl -n kube-system delete ds kube-proxy
  kubectl -n kube-system delete cm kube-proxy
  ```
  > 删之前最好导出一份备份（本环境当时直接删了，回滚要靠 kubeadm 重新生成 addon）。
- **验证**：
  ```bash
  kubectl get cm cilium-config -n kube-system -o jsonpath='{.data.kube-proxy-replacement}'; echo   # true
  kubectl -n kube-system exec ds/cilium -c cilium-agent -- cilium-dbg status | grep -E 'KubeProxyReplacement|Routing'
  # 期望：KubeProxyReplacement: True  [ens3 10.100.10.x (Direct Routing)]
  kubectl get ds kube-proxy -n kube-system       # NotFound
  kubectl get gatewayclass cilium -o jsonpath='{.status.conditions[0].status}'; echo   # True
  kubectl run nettest --image=harbor.wuxing.local/library/busybox:1.38.0 --restart=Never --command -- sleep 600
  kubectl exec nettest -- nc -zv -w5 10.233.0.1 443    # open（迁移前是超时）
  ```
- **回滚**：
  ```bash
  helm upgrade cilium /data1/ssdxt/charts/cilium-1.20.1.tgz -n kube-system \
    -f /data1/ssdxt/cilium-values-before-kpr.yaml \
    --set kubeProxyReplacement=false --set gatewayAPI.enabled=false --timeout 15m
  # 重新部署 kube-proxy：kubeadm init phase addon kube-proxy --config <kubeadm-config>
  kubectl -n kube-system rollout restart ds/cilium
  ```

---

## §2 kube-vip 部署（API VIP 10.100.10.250）

**【原有功能】** kube-vip 由 kk 以静态 Pod 形式部署在 3 台 control（`/etc/kubernetes/manifests/kube-vip.yaml`），
ARP 模式抢 VIP 10.100.10.250:6443，apiserver/组件全部走 VIP。

**【后补调整】** 只有一处：租约参数（演变史与去重脚本见 **20-系统层 §4**）。
现状 30/20/5；换盘后建议 15/5/2。Gateway 的 LoadBalancer IP（10.100.10.251）也由
kube-vip 的 service pool 分配（需 `svc_enable: "true"`，见 §3 验证）。

验证：
```bash
kubectl -n kube-system get pods | grep kube-vip        # 3 个 1/1 Running
curl -k --noproxy '*' --max-time 8 https://10.100.10.250:6443/healthz   # ok
```

---

## §3 Gateway API（CRD v1.6.1 experimental + CiliumLB IPPool + HTTPRoute）

**【原有功能】** Cilium 1.20.1 内置 Gateway API 控制器（`io.cilium/gateway-controller`），
KPR=true 时自动生效；对外暴露用 Gateway + HTTPRoute，LoadBalancer IP 由 kube-vip/Cilium LB 分配。

**【后补调整】**

1. **装 CRD v1.6.1 experimental（Cilium 1.20 要求 ≥v1.6.1；第一次装 v1.2.1 版本太低报错）**。
   CRD 文件已在离线资产里：
   ```bash
   kubectl apply --server-side --force-conflicts -f /data1/ssdxt/charts/gateway-api/experimental-install.yaml
   ```
   - 为什么 `--server-side`：普通 apply 报
     `The CustomResourceDefinition "httproutes..." is invalid: metadata.annotations: Too long: may not be more than 262144 bytes`
     （CRD 大注解超限，90-踩坑 §10）。
   - 验证版本都到 v1：
     ```bash
     kubectl get crd tlsroutes.gateway.networking.k8s.io -o jsonpath='{.spec.versions[*].name}'; echo    # v1 v1alpha2 v1alpha3
     kubectl get crd grpcroutes.gateway.networking.k8s.io -o jsonpath='{.spec.versions[*].name}'; echo   # v1
     ```
2. **给 Gateway 分配固定 IP：CiliumLoadBalancerIPPool（注意用 `spec.blocks`）**：
   ```bash
   kubectl apply -f - <<'YAML'
   apiVersion: cilium.io/v2
   kind: CiliumLoadBalancerIPPool
   metadata:
     name: gateway-pool
   spec:
     blocks:
     - cidr: 10.100.10.251/32     # 注意字段是 spec.blocks（新版本 API），不是 spec.cidrs
   YAML
   ```
3. **部署 Gateway + HTTPRoute（域名分流）**——直接跑资产脚本：
   ```bash
   bash /data1/ssdxt/gateway/01-deploy.sh
   ```
   它会：建 `gateway` 命名空间 → 建 Gateway（`gatewayClassName: cilium`，HTTP 80，
   `allowedRoutes.from: All`）→ 在 gateway 命名空间建 4 个 ExternalName 服务别名
   （Grafana/Prometheus/Alertmanager/Longhorn，Gateway 不能直接跨命名空间引 Service）→
   建 HTTPRoute 按 `grafana/prometheus/alertmanager/longhorn.wuxing.local` 分流。
4. **跨命名空间后端：ReferenceGrant**（若后端 Service 与 Gateway 不同命名空间且不用 ExternalName
   别名，需在后端命名空间放行）：
   ```bash
   kubectl apply -f - <<'YAML'
   apiVersion: gateway.networking.k8s.io/v1beta1
   kind: ReferenceGrant
   metadata:
     name: allow-gateway-ns
     namespace: monitoring          # 放在"被引用方"命名空间
   spec:
     from:
     - group: gateway.networking.k8s.io
       kind: HTTPRoute
       namespace: gateway
     to:
     - group: ""
       kind: Service
   YAML
   ```
5. **访问方式**：
   - 域名（推荐）：访问者机器 hosts 加
     `10.100.10.251 grafana.wuxing.local prometheus.wuxing.local alertmanager.wuxing.local longhorn.wuxing.local`
   - Grafana 也可走节点 NodePort：`https://<任一节点IP>:32298`（如 `10.100.10.10:32298`，admin/<GRAFANA_PASSWORD>）
   - **2026-09-30 起已 HTTPS 化（cert-manager 自建 CA 泛域名证书）并接入 ArgoCD 域名，详见 §6：[gateway-https.md](gateway-https.md)**；
     工位（无 .251 路由）统一走 `https://<域名>:32298`
- **验证**：
  ```bash
  kubectl get gateway -n gateway
  # NAME                 CLASS    ADDRESS         PROGRAMMED   AGE
  # monitoring-gateway   cilium   10.100.10.251   True         ...
  kubectl get httproute -A
  curl -s -H 'Host: grafana.wuxing.local' http://10.100.10.251/api/health
  ```
- **回滚**：`kubectl delete httproute/gateway/ReferenceGrant/CiliumLoadBalancerIPPool` 对应对象；
  彻底回滚随 §1 的 cilium 回滚（gatewayAPI.enabled=false）。

---

## §4 nodelocaldns（169.254.25.10）

**【原有功能】** 无（kk 配了 kubelet clusterDNS 指向 169.254.25.10，但**从不自动部署** nodelocaldns，
Pod DNS 全断——这是装完必现的坑）。

**【后补调整】** 部署 nodelocaldns DaemonSet（资产：`/data1/ssdxt/charts/nodelocaldns.yaml`，
镜像 `harbor.wuxing.local/dns/k8s-dns-node-cache:1.26.7`）：

```bash
kubectl apply -f /data1/ssdxt/charts/nodelocaldns.yaml
```

关键配置：
- `args` **只保留三个**：`-localip=169.254.25.10`、`-conf=/etc/Corefile`、`-upstreamsvc=kube-dns`
  （该版本加 `-healthTimeout` 会打印 usage 后 exit 2）；
- hostNetwork=true（绑节点 link-local 地址）、privileged=true、dnsPolicy=Default、tolerations Exists；
- Corefile 上游 = `10.233.0.10`（kube-dns ClusterIP，force_tcp）。

**两层 DNS 解析关系**：
```
Pod /etc/resolv.conf → 169.254.25.10（节点本机 nodelocaldns，缓存）
                        ↓ miss
                      10.233.0.10（CoreDNS，cluster.local 权威）
                        ↓ 外部域名
                      节点 /etc/resolv.conf 上游（本环境离线 → 见 §5）
```

- **验证**：
  ```bash
  kubectl get ds nodelocaldns -n kube-system        # 期望 11/11
  kubectl exec nettest -- cat /etc/resolv.conf      # nameserver 169.254.25.10
  kubectl exec nettest -- nslookup kubernetes.default.svc.cluster.local   # Address: 10.233.0.1
  ```
- **回滚**：`kubectl delete -f /data1/ssdxt/charts/nodelocaldns.yaml` **必须同时**把 11 台节点
  kubelet 的 clusterDNS 改回 `10.233.0.10` 并重启 kubelet，否则 Pod DNS 再断：
  ```bash
  ssh root@$ip "sed -i 's/^\( *\)- 169.254.25.10/\1- 10.233.0.10/' /var/lib/kubelet/config.yaml && systemctl restart kubelet"
  ```

---

## §5 已知问题：CoreDNS forward 223.5.5.5 离线超时刷错误日志（未修，待决策）

**【现状】** CoreDNS Corefile 里保留了 `forward . 223.5.5.5` 一类外部上游。离线环境该地址不可达，
CoreDNS 持续刷 `dial: i/o timeout` 类错误日志（Loki 里可见 `{namespace="kube-system",pod=~"coredns.*"}`
错误持续出现）。仅影响日志噪音与少量超时等待，不影响 cluster.local 解析。

**【候选方案（待决策，未实施）】** ① 删掉外部 forward 段（最干净，外部域名将无法解析——本环境
本就无外网）；② forward 指向内网 DNS（若有）；③ 保留 + 降噪。**决策前不要动**，新环境复刻时
若客户有内网 DNS，把 forward 改为该地址即可顺带解决。

---

## §6 Gateway HTTPS 化（cert-manager 自建 CA + *.wuxing.local 泛域名 + ArgoCD 域名接入 + NodePort 清理）

**【后补调整】**（2026-09-30）证书体系、Gateway 443 监听、nodePort 32298 固定为 HTTPS 的关键坑
（Cilium 会重建 gateway svc，必须按 `port-80`/`port-443` 端口名 patch）、HTTP→HTTPS 跳转、
NodePort 清理与端到端验证——全文见 **[gateway-https.md](gateway-https.md)**。

---

## §7 Gateway/Hubble 可观测性（Hubble Relay+UI + 指标接入 Prometheus）

**【后补调整】**（2026-09-30）Hubble Relay/UI（`https://hubble.wuxing.local:32298`）、cilium/envoy/agent
指标接入 kube-prometheus-stack（ServiceMonitor 带 `release: prometheus-stack` 标签）、Grafana 面板
`Cilium Gateway (wuxing.local)`。两个坑：hubble-peer `internalTrafficPolicy: Local` 导致 relay 起不来；
ExternalName 别名作 Gateway 后端 503（要直引真服务+ReferenceGrant）。全文见 **[hubble-observability.md](hubble-observability.md)**。

---

## §8 Cilium 全栈能力（统一 values + WireGuard / BandwidthManager / EgressGateway / BGP）

**【后补调整】**（2026-09-30）统一 values 成为唯一事实来源
（`/data1/ssdxt/values/cilium-values-unified.yaml`），一次性启用 WireGuard 加密、
Bandwidth Manager、Egress Gateway、BGP Control Plane 四开关并全套回归通过；
含 helm upgrade 铁律（禁 --wait、升级后 3 补丁）、回归清单、BGP/Egress 示例 CR、
Tetragon 路线。全文见 **[cilium-full-stack.md](cilium-full-stack.md)**。

---

## §9 Kyverno 出网代理注入（集群出网管控第一步）

**【后补调整】**（2026-09-30）Kyverno 1.19.1（chart 3.9.1）离线安装（Harbor `kyverno/` 项目，
`background/reports-controller` 关闭、`forceFailurePolicyIgnore` 兜底、kube-system webhook 排除），
ClusterPolicy `inject-proxy-env`：给带 `wxq.io/egress-proxy=enabled` 标签的命名空间里的所有 Pod
自动注入 `http(s)_proxy=10.100.10.14:8888` + NO_PROXY 清单。选型/语法/验证/回滚全文见
**[kyverno-egress-injection.md](kyverno-egress-injection.md)**。
