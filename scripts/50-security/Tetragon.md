# Tetragon —— eBPF 运行时安全（可观测 + 策略）

> 章节：85-安全。基线事实以 [00-环境清单.md](../00-环境清单.md) 为准。
> 组件：Cilium 同门的 eBPF 安全运行时（Cilium 系），提供进程/文件/网络事件实时追踪与安全策略。
> 版本：Chart **1.7.1**（App Version 1.7.1），安装日期 2026-09-30，K8s 1.37 兼容（chart 无版本上限约束，DaemonSet 在内核 5.15.167 上正常加载 BPF）。

## 【原有功能】是什么 / 为什么

**是什么**：Tetragon 通过 eBPF kprobe 直接在内核态追踪进程执行（execve）、文件访问、网络连接等事件，配合 TracingPolicy CRD 做细粒度观察或阻断（enforcement）。事件以 JSON 从 `export-stdout` sidecar 输出，指标暴露在 2112 端口（Prometheus 格式）。

**为什么**：集群缺运行时安全层。Cilium 管网络，Tetragon 管"容器里进程在干什么"——谁读了 /etc/shadow、谁在 kube-system 里起了 shell。开箱以**观察（observe）**为主，不动业务流量，零依赖集群代理。

**核心资源**：
- `TracingPolicy`（集群级）/ `TracingPolicyNamespaced`（命名空间级），apiVersion `cilium.io/v1alpha1`，由 tetragon-operator 负责安装 CRD
- 组件：`tetragon` DaemonSet（每节点 BPF 采集，2 容器：tetragon + export-stdout）、`tetragon-operator` Deployment（CRD 生命周期 + 指标 2113）

## 镜像清单（全部已入 Harbor，显式 tag 无 digest）

| 源镜像 | Harbor |
|---|---|
| quay.io/cilium/tetragon:v1.7.1 | harbor.wuxing.local/tetragon/tetragon:v1.7.1 |
| quay.io/cilium/tetragon-operator:v1.7.1 | harbor.wuxing.local/tetragon/tetragon-operator:v1.7.1 |
| quay.io/cilium/hubble-export-stdout:v1.1.1 | harbor.wuxing.local/tetragon/hubble-export-stdout:v1.1.1 |
| quay.io/cilium/tetragon-rthooks:v0.8（默认不启用，备用） | harbor.wuxing.local/tetragon/tetragon-rthooks:v0.8 |

Harbor 项目 `tetragon`（public），mirror.sh 已补 `LIST_TETRAGON`（`bash /data1/ssdxt/images/mirror.sh tetragon`）。
Chart 离线包：`/data1/ssdxt/charts/tetragon-1.7.1.tgz`。

## 安装命令（幂等）

资产目录 `/data1/ssdxt/security/`：

```bash
# control-01 上执行（helm 从本地 tgz，无外网依赖）
bash /data1/ssdxt/security/01-install-tetragon.sh
```

等效手工步骤：

```bash
export KUBECONFIG=/etc/kubernetes/admin.conf
helm install tetragon /data1/ssdxt/charts/tetragon-1.7.1.tgz \
  -n tetragon --create-namespace \
  -f /data1/ssdxt/security/tetragon-values.yaml
kubectl apply -f /data1/ssdxt/security/policies-baseline.yaml
kubectl apply -f /data1/ssdxt/security/tetragon-dashboard-cm.yaml
```

**values 要点**（`tetragon-values.yaml`）：
- 三个镜像全部指向 Harbor（`harbor.wuxing.local/tetragon/*`），显式 tag；
- `tetragon.prometheus.serviceMonitor.enabled=true`，labelsOverride `release: prometheus-stack`（metrics 端口 **2112**，注意 1.x chart 默认已不是旧文档说的 9943）；
- **覆盖默认 exportDenyList**：chart 默认丢弃 `kube-system`/`cilium`/host 事件，与 kube-system execve 观察策略冲突，改为只丢弃 `health_check` + host("") + cilium：

```yaml
tetragon:
  exportDenyList: |-
    {"health_check":true}
    {"namespace":["", "cilium"]}
```

## 策略说明（开箱基线，全观察不阻断）

文件 `policies-baseline.yaml`，5 条：

| 策略 | 类型 | 内容 |
|---|---|---|
| sensitive-file-shadow | TracingPolicy | kprobe `security_file_permission`，arg0 Equal `/etc/shadow` |
| sensitive-file-sudoers | TracingPolicy | 同上，Equal `/etc/sudoers` |
| sensitive-file-kubernetes-dir | TracingPolicy | 同上，**Prefix** `/etc/kubernetes/`（命中所有 kubeconfig/pki 读访问） |
| shell-exec-kube-system | TracingPolicyNamespaced (kube-system) | kprobe `sys_execve`（syscall: true），观察命名空间内全部 execve |
| shell-exec-monitoring | TracingPolicyNamespaced (monitoring) | 同上 |

**1.7.x CRD 语法要点（踩坑沉淀）**：
- `message` 在 `kprobes[]` 级（不是 spec 级也不是 selector 级）；
- `matchArgs` 匹配值字段是 **`values`（列表）**，不是 `value`；
- execve 系统调用要写 **`call: "sys_execve"` + `syscall: true`**；写裸 `execve` 会报 `syscall "__x64_execve" not found` 加载失败。

## 验证输出（2026-09-30 实测）

```text
$ kubectl -n tetragon get pods        # 11 节点集群
tetragon-*                           2/2  Running   11/11（每节点一个，DS tetragon 11/11 Ready）
tetragon-operator-c85c6cbd9-*        1/1  Running

$ kubectl get tracingpolicies.cilium.io
sensitive-file-kubernetes-dir   sensitive-file-shadow   sensitive-file-sudoers
$ kubectl get tracingpoliciesnamespaced.cilium.io -A
kube-system   shell-exec-kube-system
monitoring    shell-exec-monitoring
$ kubectl -n tetragon logs -l app.kubernetes.io/name=tetragon -c tetragon --since=8m --prefix | grep -c 'failed loading policy'
0
```

**冒烟证据（default ns busybox pod 内 `ls /` 与 `cat /etc/shadow`）**：

```text
$ kubectl -n tetragon logs -l app.kubernetes.io/name=tetragon -c export-stdout --tail=3000 --prefix | grep tg-smoke
{"process_exec":{"process":{...,"binary":"/bin/ls","arguments":"/",...,"pod":{"namespace":"default","name":"tg-smoke",...}},"node_name":"wxq-run-08",...}}
{"process_exit":{...同上...}}

$ ... | grep process_kprobe | grep sensitive-file-shadow
{"process_kprobe":{"process":{...,"binary":"/bin/cat","arguments":"/etc/shadow",...},   ← 敏感文件策略命中
$ ... | grep process_kprobe | grep shell-exec-kube-system
{"process_kprobe":{"process":{...,"binary":"/node-cache",...,"pod":{"namespace":"kube-system","name":"nodelocaldns-xgr5m",...}}  ← execve 观察策略命中
```

> 注意：事件 JSON 在 **`export-stdout` sidecar 容器**的日志里（`-c export-stdout`），不在 tetragon 容器（那里只有组件自身日志）。也可以装 tetra CLI 直连 gRPC（unix:///var/run/tetragon/tetragon.sock）实时看。

## Grafana 看板

- 官方仓库 cilium/tetragon 已不再内置 grafana 目录，社区看板在 grafana.com：**ID 25789（Tetragon，27 panels）**；
- 已下载导入为 ConfigMap `tetragon/tetragon-dashboard-cm.yaml`（label `grafana_dashboard=1`），Grafana sidecar 自动加载；
- 验证：`GET /api/search?query=Tetragon` 返回 `{"title":"Tetragon","uid":"1549477177261559549","url":"/d/1549477177261559549/tetragon"}` ✅；
- 打开看板后需手动把数据源选为 Prometheus（本集群数据源）；指标名以 `tetragon_` 前缀（如 `tetragon_process_exec_total`）；
- Prometheus 抓取：ServiceMonitor `tetragon/tetragon`、`tetragon/tetragon-operator`（label release=prometheus-stack），targets 中 11 个 tetragon 端点已 active ✅。

重新生成看板 CM（版本升级时）：WSL 里
`curl -sL 'https://grafana.com/api/dashboards/25789/revisions/latest/download' -o tetragon.json`（走 HTTPS_PROXY），
然后 `bash /data1/ssdxt/security/gen-dashboard-cm.sh tetragon.json tetragon-dashboard-cm.yaml`。

## 日常使用（tetra CLI 示例）

```bash
# 1) 直接看事件流（任选一个节点上的 tetragon pod）
kubectl -n tetragon exec <tetragon-pod> -c tetragon -- /usr/bin/tetra getevents -o compact
# 注意 getevents 是流式命令，不会自动退出，用 timeout 15 包一层

# 2) 过滤命名空间 + compact 输出
kubectl -n tetragon exec <tetragon-pod> -c tetragon -- /usr/bin/tetra getevents -o compact --namespaces default

# 3) 看某条策略最近命中（导出日志侧）
kubectl -n tetragon logs -l app.kubernetes.io/name=tetragon -c export-stdout --tail=2000 --prefix \
  | grep process_kprobe | grep sensitive-file

# 4) 敏感文件访问事件带 Pod/容器/节点全上下文，可直接定位来源
```

不装 CLI 时也可在节点上直接看 `/var/run/cilium/tetragon/tetragon.log`（rotation 10MB×5，由 export-stdout 消费）。

## 后续路线：enforcement（阻断）怎么开

当前基线全部是观察；Tetragon 支持 kprobe enforcer / LSM 两种阻断，开启方法与风险：

1. **快速阻断（kprobe override，同一策略内）**：selector 加 `matchActions: [{action: Sigkill}]` 或 kprobe 加 `override: true` + `returnArgAction: SigKill`，即"读 /etc/shadow 直接杀进程"。
   - 风险：**误杀**。内核路径匹配是全局的（kprobe 不分容器/宿主），`/etc/shadow` 策略会覆盖宿主机进程；先观察至少 1-2 周基线事件，确认无正常业务命中再启用。
2. **LSM hook 阻断**：策略 `lsmhooks: [{hook: "file_open", args: [...], selectors: [... matchActions: Sigkill/SigTrap]}]`，需内核 5.7+ 且 BPF LSM 已启用（`lsm=bpf` 内核参数）——**当前内核 5.15 默认未启用 bpf LSM，需要逐节点改内核启动参数并重启**，属于大动作，单独评审。
3. **建议顺序**：观察基线 → 高置信策略（如 execve 拒绝清单：crypto miner 二进制特征）小范围 enforcement → 全量。任何 enforcement 变更按军规先在本文档记【后补调整】。

## 回滚

```bash
export KUBECONFIG=/etc/kubernetes/admin.conf
kubectl delete -f /data1/ssdxt/security/policies-baseline.yaml   # 只撤策略
kubectl -n tetragon delete cm tetragon-dashboard                 # 只撤看板
helm uninstall tetragon -n tetragon                              # 全量卸载（CRD 由 operator 删除或手工 kubectl delete crd）
```
