# Kyverno 离线安装 + 按命名空间标签自动注入代理环境变量（集群出网管控第一步）

> 2026-09-30 落地。目标：**给打了指定标签的命名空间里的所有 Pod，自动注入 http(s)_proxy 等环境变量**，
> 出网统一走集群代理 `http://10.100.10.14:8888`（tinyproxy），未打标签的命名空间完全不受影响。
> 资产：`/data1/ssdxt/charts/kyverno-3.9.1.tgz`、`/data1/ssdxt/security/kyverno/`（values + 策略 + 安装/镜像脚本）。

---

## §1 选型：为什么是 Kyverno（而不是 Gatekeeper）

| 维度 | Kyverno | Gatekeeper (OPA) |
|---|---|---|
| 策略语言 | YAML（patchStrategicMerge，与 k8s 原生写法一致） | Rego（独立语言，学习成本高） |
| mutate 注入 env | 一等公民，几行 YAML | 变更类需求要写 Rego patch，繁琐 |
| 上手/交接成本 | 低（运维可直接读改） | 高 |
| 生态 | 官方 pod-security 策略集、镜像校验 verifyImages | Constraints 模板库大 |

本需求是 **mutate 注入 env**，Kyverno 的 patchStrategicMerge 就是为这类场景设计的；后续 PSS 基线、
镜像签名校验它也能覆盖。选 Kyverno。

- Chart `kyverno/kyverno 3.9.1`，App 版本 **v1.19.1**（截至 2026-09-30 最新稳定版）。
- ⚠️ 1.19 官方提示 `kyverno.io/v1 ClusterPolicy` 已标记弃用（未来迁 `policies.kyverno.io` 的
  MutatingPolicy 等 CEL 系），当前版本完全可用；迁移时再评估。

## §2 离线镜像清单（Harbor `kyverno/` 项目，amd64，显式 tag，无 digest）

| 镜像 | 用途 |
|---|---|
| `harbor.wuxing.local/kyverno/kyverno:v1.19.1` | admission-controller 主容器 |
| `harbor.wuxing.local/kyverno/kyvernopre:v1.19.1` | admission-controller init（升级前备份） |
| `harbor.wuxing.local/kyverno/cleanup-controller:v1.19.1` | cleanup controller（保留，轻量） |
| `harbor.wuxing.local/kyverno/kyverno-cli:v1.19.1` | helm post-upgrade `migrate-resources` hook Job（**漏搬会导致 helm 显示 failed**） |
| `harbor.wuxing.local/kyverno/readiness-checker:v1.19.1` | helm test |
| `harbor.wuxing.local/library/curl:8.16.0` | 验证 Pod 用（curl 走代理不做本地 DNS 解析，busybox wget 会先本地解析而失败） |

镜像搬运：WSL 里跑 `bash /data1/ssdxt/security/kyverno/mirror.sh`（源走 `HTTPS_PROXY=http://127.0.0.1:12450`，
Harbor 直连加 `NO_PROXY=harbor.wuxing.local,10.100.10.29`，`--dest-tls-verify=false --dest-creds admin:***`）。
Harbor 项目用 API 建（幂等，409=已存在）：
`curl -sk -u admin:*** -X POST https://harbor.wuxing.local/api/v2.0/projects -d '{"project_name":"kyverno","public":false}'`

## §3 安装（values 关键决策）

```bash
export KUBECONFIG=/etc/kubernetes/admin.conf
helm upgrade --install kyverno /data1/ssdxt/charts/kyverno-3.9.1.tgz \
  -n kyverno --create-namespace -f /data1/ssdxt/security/kyverno/values.yaml --timeout 10m
```

values（`/data1/ssdxt/security/kyverno/values.yaml`）四个关键点：

1. **webhook 绝不阻塞全集群**：`features.forceFailurePolicyIgnore.enabled: true`
   → Kyverno 把 resource webhook 注册为 `Ignore`（实测
   `kyverno-resource-mutating-webhook-cfg / mutate.kyverno.svc-ignore failurePolicy=Ignore`）。
   **注意该键在顶层 `features:` 下，不是 `config:` 下**（放错位置 chart 静默忽略，arg 仍是 false）。
   含义：Kyverno 挂了/超时，Pod 照常创建，只是漏注入——出网管控宁可漏、不可阻。
   （policy 级 webhook 如 `kyverno-policy-validating-webhook-cfg` 仍为 Fail，那类对象只有 Kyverno
   自己管理策略时才碰，不拦截业务 Pod，无阻塞风险。）
2. **kube-system / kyverno 绝不进 webhook**：`config.webhooks.namespaceSelector` NotIn 排除两个命名空间。
   kube-system 核心组件本无外网需求，且避免任何 webhook 往返；kube-system 未打标签，策略层同样不命中（双保险）。
3. **减负载**：`backgroundController.enabled: false`、`reportsController.enabled: false`
   （本场景只做准入期 mutate，策略 `background: false`，不需要后台扫描与策略报告两个大 informer）。
4. **镜像全指 Harbor**：`global.image.registry: harbor.wuxing.local` + 各组件显式 `tag: v1.19.1`。

验证：`kubectl -n kyverno get pods`（admission-controller 2 副本 + cleanup-controller 均 Running）、
`helm list -n kyverno` STATUS=deployed。

## §4 注入策略（逐段解释）

`/data1/ssdxt/security/kyverno/inject-proxy-policy.yaml`：

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: inject-proxy-env
spec:
  background: false                # 只在准入时评估，不做后台扫描（也不依赖已关闭的 background-controller）
  validationFailureAction: Audit   # 1.19 起不再支持 "Ignore"，Audit 即"只报不阻"：策略求值异常不阻塞 Pod 创建
  rules:
    - name: inject-proxy-env-on-labeled-ns
      match:
        any:
          - resources:
              kinds: [Pod]
              namespaceSelector:       # ★ 按命名空间标签开关：只命中 wxq.io/egress-proxy=enabled 的 ns
                matchLabels:
                  wxq.io/egress-proxy: enabled
      mutate:
        patchStrategicMerge:
          spec:
            containers:
              - (name): "*"            # strategic merge 以 name 为 merge key，"*" 锚点=匹配所有容器
                env:
                  - {name: http_proxy,  value: http://10.100.10.14:8888}
                  - {name: https_proxy, value: http://10.100.10.14:8888}
                  - {name: HTTP_PROXY,  value: http://10.100.10.14:8888}
                  - {name: HTTPS_PROXY, value: http://10.100.10.14:8888}
                  - {name: no_proxy, value: "localhost,127.0.0.1,.svc,.svc.cluster.local,.cluster.local,10.233.0.0/16,10.96.0.0/12,10.100.10.0/24,.wuxing.local,harbor.wuxing.local,10.100.10.29,kubernetes.default"}
                  - {name: NO_PROXY, value: "同上"}
```

要点：

- **namespaceSelector 写在 `match.resources` 里**（1.13+ 语法），不要用 preconditions 拼
  `request.namespaceObject.metadata.labels.wxq\.io/egress-proxy`——带点/斜杠的 label key 转义极易错。
- patch 里容器条目**必须带 `(name): "*"`**：strategic merge 需要 merge key；
  只写 `env:` 不带 name 会把补丁合坏，apiserver 报 `spec.containers: Required value`。
- chart 会**自动生成 autogen 规则**（对 Deployment/StatefulSet/DaemonSet/Job/CronJob 在
  Pod template 层注入，见 `kubectl get cpol inject-proxy-env -o jsonpath='{.status.autogen}'`），
  所以工作负载同样生效。
- **NO_PROXY 清单说明**：service 网段（10.96/12，nodelocaldns/cluster.local 域）、Pod 网段
  （10.233/16）、节点网段（10.100.10.0/24）、内网域名（.wuxing.local，含 Harbor）、
  Harbor IP（10.100.10.29）、`kubernetes.default`。拉镜像、访问集群内服务绝不能绕道代理。
- **使用方式**：`kubectl label ns <ns> wxq.io/egress-proxy=enabled` 即开，`disabled` 或删标签即关，
  对存量 Pod 需重建（删除标签不会回滚已注入的 env）。
- **状态验证**：`kubectl get cpol inject-proxy-env` → `READY True, MESSAGE Ready`。

## §5 验证记录（实测输出）

```bash
kubectl create ns egress-test && kubectl label ns egress-test wxq.io/egress-proxy=enabled
kubectl create ns egress-ctrl    # 不打标签，对照组
```

① 打标 ns 的 Pod 自动注入 6 个 env（4 个 proxy + 2 个 no_proxy）：

```
$ kubectl get pod egress-test-pod -n egress-test -o jsonpath='{range .spec.containers[0].env[*]}{.name}={.value}{"\n"}{end}'
http_proxy=http://10.100.10.14:8888
https_proxy=http://10.100.10.14:8888
HTTP_PROXY=http://10.100.10.14:8888
HTTPS_PROXY=http://10.100.10.14:8888
no_proxy=localhost,127.0.0.1,.svc,...,kubernetes.default
NO_PROXY=localhost,127.0.0.1,.svc,...,kubernetes.default
```

② 出网实测（tinyproxy 国内直连可用；github 的 CONNECT 有上游问题）：

```
$ kubectl exec -n egress-test egress-test-pod -- curl -s --max-time 10 -o /dev/null -w '%{http_code}\n' http://www.baidu.com
200
$ kubectl exec -n egress-test egress-test-pod -- curl -s --max-time 10 -o /dev/null -w '%{http_code}\n' https://www.baidu.com
200
```

③ 未打标 ns 对照（无注入、无法出网——本集群 CoreDNS 无外部上游，curl 无代理时报 DNS 错，符合预期）：

```
$ kubectl get pod egress-ctrl-pod2 -n egress-ctrl -o jsonpath='{.spec.containers[0].env}'
""                                        # 空 = 未注入
$ kubectl exec -n egress-ctrl egress-ctrl-pod2 -- curl -s --max-time 8 -o /dev/null -w '%{http_code}' http://www.baidu.com
000   # exit 6 = couldn't resolve host
```

④ kube-system 无注入：它没打 `wxq.io/egress-proxy` 标签，且在 webhook namespaceSelector NotIn 里，
核心组件零感知（kube-system Pod 重启数 0，未发生任何滚动重启）。

> 坑：验证镜像**必须用 curl**（`library/curl:8.16.0`），busybox wget 走代理仍会先本地解析域名，
> 在 CoreDNS 无外部上游的离线集群里必然失败（本手册 30 章 §5 的已知问题）。

## §6 扩展方向（后续用同一套 Kyverno 做）

1. **镜像校验**：`verifyImages` 策略强制业务镜像来自 `harbor.wuxing.local/*`（防外来镜像）。
2. **PSS 安全基线**：直接引用官方 pod-security 策略集（restricted），按命名空间标签灰度启用。
3. **标签校验**：`validate` 策略强制业务 ns 必须带 `team/owner` 标签（配 validationFailureAction 按需 Audit/Enforce）。
4. 注意：`validationFailureAction` 与"是否阻塞"直接相关——管控类策略可逐步升 Enforce，但
   `features.forceFailurePolicyIgnore=true` 只兜底 failurePolicy，不改变主动 Enforce 的拦截行为。

## §7 回滚

```bash
# 只回滚注入策略（最小动作）
kubectl delete cpol inject-proxy-env
# 彻底下线 Kyverno（resource webhook 是 Kyverno 自管的，删 release 前先看 hook 是否清理干净）
helm uninstall kyverno -n kyverno
kubectl delete ns kyverno
# 确认无残留 webhook（否则会阻塞 Pod 创建）
kubectl get mutatingwebhookconfiguration,validatingwebhookconfiguration | grep kyverno
```

卸载前若 webhook 残留且 failurePolicy=Fail，务必手工删除对应 webhookconfiguration，否则全集群 Pod 创建被阻塞。
