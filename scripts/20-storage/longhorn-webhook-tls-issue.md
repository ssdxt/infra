# Longhorn webhook TLS Secret 抖动问题 — 诊断报告

- 诊断时间：2026-09-29 16:00~16:10（CST）
- 集群：K8s v1.37.0，11 节点，Longhorn v1.7.2（DaemonSet 8 个 manager pod）
- 结论：**命中 Longhorn 上游已知问题 #13012**，属于「多 manager 实例争抢同一个 webhook TLS Secret」的自持循环
- 诊断阶段为只读；**方案 A 已于 2026-09-29 16:11 经批准后执行**（见 §0）

---

# ⚠️ §0 证书到期台账（最高优先级，请登记到运维日历）

方案 A 给两个 Secret 打上了 `listener.cattle.io/static="true"`，**dynamiclistener 从此不再自动续期**。必须手工轮转；忘记的后果是 **webhook TLS 证书过期 → Longhorn admission webhook 全量失败（failurePolicy=Fail）→ 无法创建/修改任何 Longhorn CR**。

| 对象 | 备份文件 | 生效日 | **到期日** | 处理期限 |
|---|---|---|---|---|
| **leaf 证书** `longhorn-system/longhorn-webhook-tls` | `storage/backup/longhorn-webhook-leaf-0929-1610.pem` | 2026-09-29 | **2027-09-29** | **必须在 2027-08 之前完成轮转**（留 1 个月缓冲） |
| **CA 证书** `longhorn-system/longhorn-webhook-ca` | `storage/backup/longhorn-webhook-ca-0929-1610.pem` | 2026-09-29 | **2036-09-26** | 2036 年（远期，可忽略） |

- leaf 有效期 365 天，CA 有效期 10 年。
- 两个 Secret 的完整 yaml 备份：`/data1/ssdxt/storage/backup/longhorn-webhook-secrets-0929-1610.yaml`
- **轮转方法（届期执行）**
  1. 先备份：`kubectl -n longhorn-system get secret longhorn-webhook-ca longhorn-webhook-tls -o yaml > backup.yaml`
  2. 移除 static 注解、让 dynamiclistener 恢复自动签发：
     `kubectl -n longhorn-system annotate secret longhorn-webhook-ca listener.cattle.io/static-`
     `kubectl -n longhorn-system annotate secret longhorn-webhook-tls listener.cattle.io/static-`
  3. 重启 manager 触发重签：`kubectl -n longhorn-system rollout restart ds/longhorn-manager`
  4. **注意**：这样做会**把 §1 的抖动问题带回来**。更稳妥的路线是届时直接升级到已修复的 Longhorn（≥ v1.11.3），或按 §3 方案 C 用 helm 预置长有效期静态证书。

## §0.1 方案 A 执行结果（2026-09-29 16:11~16:28）

```bash
kubectl -n longhorn-system annotate secret longhorn-webhook-ca  listener.cattle.io/static=true --overwrite
kubectl -n longhorn-system annotate secret longhorn-webhook-tls listener.cattle.io/static=true --overwrite
kubectl -n longhorn-system rollout restart ds/longhorn-manager
```

| 指标 | 修复前 | 修复后（干净窗口 16:19） | 变化 |
|---|---|---|---|
| Secret `resourceVersion` 60s 增量 | **+474 / 31s（≈15 写/秒）** | **0 / 60s** | **抖动完全停止** |
| `secrets PUT` code=409 | 210.8 /s | **0 / s** | **-100%** |
| `secrets PUT` code=200（提交=etcd 写入） | 12.7 /s | **0.0037 /s** | **-99.97%** |
| 全部 apiserver 请求 | 485 /s | **15.7 /s** | **-96.8%** |
| 全部写请求 | 216 /s | **5.0 /s** | **-97.7%** |
| mutating 队列深度（5m max） | **204** | **11** | **-95%** |
| `429` terminations（secrets） | 1166 / 10m | **0 / 5m** | **归零** |
| static 注解存活 | — | 2/2（3 次采样） | 未被覆盖 |

功能复验（均通过）：
- **admission webhook 正常**：`kubectl apply --dry-run=server` 造非法 Volume 仍被正确拒绝 → `The request is invalid: : invalid volume frontend specified:`（证明证书分发到 8 个 pod 正常、webhook 未损坏）
- **Longhorn 数据面正常**：新建 1Gi PVC（storageClass=longhorn）**13 秒内 Bound**（`pvc-e33db8b9-…`），验完已清理
- `longhorn-manager` DaemonSet 滚动完成 8/8；longhorn 47 个 Pod 全部 Running、无异常

残余观察（8 分钟静默期，用 `restartCount` 正确统计）：

| 组件 | 修复前崩溃（<15min） | 修复后 8 分钟增量 |
|---|---|---|
| CSI（provisioner/attacher/resizer/snapshotter） | 3 | **+2** |
| cilium-operator | 2 | **+1** |

→ **未完全归零**。但此时 apiserver 总请求已降到 15/s、429 归零、mutating 队列 1~11，说明**应用层压力已消除，残余抖动来自基础设施层**（etcd 磁盘 fsync 延迟，见 `etcd-disk-requirement.md`）。需在 etcd 监控打通后（§7）继续定位。

---

## 1. 谁在写、频率多高、为什么

### 1.1 谁在写
写者不是 Longhorn 自己的证书逻辑，而是 Longhorn 内嵌的 Rancher **dynamiclistener** 库：

```
secret/longhorn-system/longhorn-webhook-tls
  annotations:
    listener.cattle.io/cn-longhorn-admission-webhook.longhor-59584d : longhorn-admission-webhook.longhorn-system.svc
    listener.cattle.io/cn-longhorn-conversion-webhook.longho-6a0089 : longhorn-conversion-webhook.longhorn-system.svc
    listener.cattle.io/fingerprint : SHA1=0840FCAF4E6C40769EE90593A051533D2B2A023B   ← 在两个值之间来回翻转
```

manager 日志里能直接看到写者与代码位置：

```
level=info msg="Updating TLS secret for longhorn-system/longhorn-webhook-tls (count: 2): map[...fingerprint:SHA1=0840FCAF...]"
  func="kubernetes.(*storage).saveInK8s" file="controller.go:225"
```

**8 个 manager pod 全都在写**（2 分钟内的写入日志行数）：

| pod | 写入日志行数 / 2min | 它持有的 fingerprint |
|---|---|---|
| longhorn-manager-8vmmc | 1481 | `CA5AD62F...46964F25` ← **少数派** |
| longhorn-manager-bq9jf | 200 | `0840FCAF...2B2A023B` |
| longhorn-manager-n4hbp | 1553 | `0840FCAF...2B2A023B` |
| longhorn-manager-t5zxk | 1452 | `0840FCAF...2B2A023B` |
| longhorn-manager-vwcmg | 1604 | `0840FCAF...2B2A023B` |
| longhorn-manager-whgpd | 1600 | `0840FCAF...2B2A023B` |
| longhorn-manager-wp8n2 | 1582 | `0840FCAF...2B2A023B` |
| longhorn-manager-zcw6v | 1512 | `0840FCAF...2B2A023B` |

关键：**集群里同时存在两张不同的 leaf 证书，7 个 pod 持 A、1 个 pod 持 B**（`8vmmc`）。两者都由同一个 CA 签发（`longhorn-webhook-ca`，CN=`dynamiclistener-ca@1790663184`），SAN 都是那两个 webhook Service DNS：

| 变体 | serial | notBefore | notAfter | SAN |
|---|---|---|---|---|
| A | `54EB1948D3B85E67` | Sep 29 06:26:24 2026 | Sep 29 06:27:21 2027 | longhorn-admission-webhook.longhorn-system.svc, longhorn-conversion-webhook.longhorn-system.svc |
| B | `1AA077907D13E187` | Sep 29 06:26:24 2026 | Sep 29 06:27:21 2027 | 同上 |

20 次采样（3s 间隔）：**distinct serial = 2，distinct fingerprint = 2，notBefore 完全相同** → 不是"每次重新签发"，而是**两张固定证书互相覆盖**。

### 1.2 频率多高
- Secret `resourceVersion` 在 57 秒内从 `1423160` 涨到 `1424126` → **+966，约 17 次写入/秒**
- `apiserver_request_total`（5 分钟窗口，3 台 apiserver 合计）：
  - `secrets PUT` 全码 **202 /s**
  - `secrets PUT code=409`（冲突被拒）**192.8 /s**
  - `secrets PUT code=200`（真正提交）**10.0 /s**
  - `secrets GET` **204 /s**
- 波动区间：冲突速率在 190~270 /s 之间浮动（10 分钟窗口曾测到 269 /s）

### 1.3 为什么反复重建（根因）
上游 issue **[longhorn/longhorn#13012](https://github.com/longhorn/longhorn/issues/13012)** 完全对得上（标题：*longhorn-manager pods race on webhook TLS Secret at scale*，在 v1.11.1 上观测到 ~200 updates/sec，官方在 v1.12.0 修复并 backport 到 v1.11.3 — [#13116](https://github.com/longhorn/longhorn/issues/13116)）：

1. **诱因（一次性的）**：pod 启动时，`dynamiclistener` 的本地 backing 还是空的，而它的 listener 已经收到了第一次 TLS 握手（admission Service 会立刻把流量路由到新 pod）。于是 `l.init.Do → updateCert(tlsName)` 读到**空 backing**，走 `factory.AddCN` **生成一张全新的、独立于 K8s 现有内容的证书**。
2. **扩散**：这张本地证书经 `factory.Merge` 的 "prefer-additional" 规则写回 K8s，覆盖掉原有证书 → 产生第二个 fingerprint。
3. **自持循环**：一旦集群里同时存在两个证书版本，`Merge` 的 prefer-additional 规则 + watch 事件延迟 会让每个 worker 反复把自己那份"稍旧的 `queuedSecret`"覆盖回去 → **无需新的启动竞争也会一直互相回滚，永不停息**。

上游原话（节选）：*"Once two distinct cert versions co-exist in different pods' backings, the prefer-additional merge rule plus watch-event lag turns into ongoing 'rollback writes' … The cycle then self-perpetuates even without further startup races."*

**为什么我们只有 8 个 manager 也会中招？** 上游说这是规模相关（几百个 pod 才会踩到），因为正常情况下 `secrets.Get` 很快、启动竞争总是被赢下。而我们这个集群 **apiserver/etcd 本来就慢**（见 `etcd-disk-requirement.md`），`secrets.Get` 往返被拖慢 → 启动竞争被输掉 → 产生证书分歧 → 进入自持循环。

> ⚠️ 这构成一个**正反馈**：etcd 慢 → 启动竞争失败 → 证书抖动 → 每秒几百次 apiserver 写请求 → apiserver/etcd 更慢 → 更容易输掉竞争。这也解释了为什么 CSI / cilium-operator 的 leader-election 会持续失租。

### 1.4 和 cert-manager 无关（已排除）
- `longhorn-system` 里没有 Certificate / Issuer / ClusterIssuer
- 两个 secret 上没有任何 `cert-manager.io/*` 注解
- cert-manager 三个 pod 健康（webhook 0 重启）
- 证书 issuer 是 `dynamiclistener-org`，不是 cert-manager

---

## 2. 对 etcd / apiserver 的量化影响

### 2.1 实测值（Prometheus，5 分钟窗口，3 台 apiserver 合计）

| 指标 | 实测值 |
|---|---|
| `secrets PUT`（全部） | **202 /s** |
| `secrets PUT` code=409（被拒） | **192.8 /s** |
| `secrets PUT` code=200（提交，= etcd 写入） | **10.0 /s** |
| `secrets GET` | **204 /s** |
| **全部写请求**（POST/PUT/PATCH/DELETE） | 216 /s |
| **全部 apiserver 请求** | 436 /s |
| secret 的 WATCH 长连接数（fan-out 倍数） | **123** |
| manager 侧 CPU 消耗 | 8 × 102~244m ≈ **1.2 核** |

### 2.2 推算的比例
- **`secrets PUT` 占全部写请求 = 202 / 216 ≈ 93.5%**
- **secrets 的 GET+PUT = 406 / 436 ≈ 93% 的全部 apiserver 请求**
- **etcd 写入：10 次/秒 × 86400 ≈ 86.4 万次写入/天**，全部来自这一个 Secret 对象
- **watch 放大：10 次提交 × 123 个 watcher ≈ 1230 个 watch 事件/秒**（每个事件都要序列化并推给 123 个 watch 流，这也是 100Mbps 内网的负担）

### 2.3 对上游前提的一处更正
> 原假设：「13 万次 409 冲突意味着 apiserver 向 etcd 叠加了海量写操作」

**409 Conflict 是被拒绝的写入，不会落到 etcd**（etcd 写入约 0），它的代价是：
1. 每次冲突前有一次 `secrets GET`（204/s）和一次完整的 admission/校验/序列化流程 → 消耗 apiserver CPU
2. **把 apiserver 的 mutating 并发队列打满**：实测 `apiserver_current_inflight_requests{request_kind="mutating"}` 长期在 40~69（APF 上限 50）→ **这才是 leases/CSI 流量被饿死、leader-election 失租的直接机制**
3. 触发 APF 限流：`apiserver_request_terminations_total{code="429"}` 中 secrets GET 565/15m、secrets PUT 492/15m（对应 http_status 429 的请求也会让客户端（含 CSI sidecar、longhorn-manager）重试，进一步放大负载）

所以结论是：**etcd 写入影响约 10 次/秒（86 万/天）不容忽视，但更大的杀伤在 apiserver 的 CPU/并发队列与 watch 放大（~1230 事件/秒）**，它与其他控制器的 lease 续期直接抢资源。

### 2.4 修掉之后的预期收益
| 项目 | 现在 | 修复后（预期） |
|---|---|---|
| Secret 写入（提交） | 10 /s | **≈ 0 /s**（仅 365 天后轮转一次） |
| Secret PUT 冲突 | 192.8 /s | **≈ 0 /s** |
| etcd 写入（该对象） | ≈86.4 万/天 | **≈ 0** |
| watch 事件 | ≈1230 /s | **≈ 0** |
| apiserver 总请求 | 436 /s | 预计降到 **~50~80 /s**（其余为 kubelet/控制器正常读取，无法精确预估） |
| 全部写请求 | 216 /s | 预计降到 **~13 /s**（≈ -94%） |
| manager CPU | ~1.2 核 | 预计降到 ~0.3 核 |

> 注：436/s 中的 secrets GET/PUT 绝大部分来自这个读写循环；正常 secret 读取（kubelet 取镜像拉取密钥、cert-manager 等）会保留，所以是"预计"而非精确值。**修复后需复测确认**（验证方法见 §3.1）。

---

## 3. 可选修复方案

### 方案 A（推荐）：给两个 Secret 加 `listener.cattle.io/static="true"` 注解
这正是上游 issue #13012 提出的解法：

```bash
kubectl -n longhorn-system annotate secret longhorn-webhook-ca  listener.cattle.io/static=true --overwrite
kubectl -n longhorn-system annotate secret longhorn-webhook-tls listener.cattle.io/static=true --overwrite
kubectl -n longhorn-system rollout restart ds/longhorn-manager
```

- **原理**：dynamiclistener 的 `IsStatic` 检查（上游 `factory/gen.go:262`）会让 `Merge` / `AddCN` / `Renew` / `updateCert` / `saveInK8s` **全部提前返回**，任何 pod 都不再写这个 Secret；证书仍通过 watch + `storage.Update` + `listener.loadCert` 路径正常分发给所有 pod，**webhook 继续可用**。
- **为什么要带重启**：注解必须在 dynamiclistener 起来之前就位，否则持旧内存状态的 pod 可能把注解覆盖掉，循环会复发。
- **风险**
  - 证书不再自动续期。当前 leaf 有效期到 **2027-09-29**，CA 到 **2036-09-26** → 有约 1 年缓冲，需要在到期前手工轮转（或届时先移除注解让它自动续期一次）。**可接受，但必须记入运维台账**。
  - `longhorn-manager` DaemonSet 滚动重启期间 Longhorn 控制面短暂中断；**卷数据面不受影响**（现有 Pod 的卷挂载、IO 继续）。
- **回滚**：`kubectl -n longhorn-system annotate secret longhorn-webhook-ca listener.cattle.io/static-` 和同样移除 tls 上的注解，再重启 ds → 恢复原行为（抖动会回来）。
- **需重启组件**：是（仅 longhorn-manager DaemonSet，滚动）

**验证方法（修复后）**
```bash
# 1) Secret 的 resourceVersion 应停止增长
kubectl -n longhorn-system get secret longhorn-webhook-tls -o jsonpath='{.metadata.resourceVersion}'; sleep 30; \
kubectl -n longhorn-system get secret longhorn-webhook-tls -o jsonpath='{.metadata.resourceVersion}'
# 2) apiserver 侧
#    sum(rate(apiserver_request_total{resource="secrets",verb="PUT",code="409"}[5m]))  → 期望 ≈0
# 3) 收益验证
#    sum(rate(apiserver_request_terminations_total{code="429"}[10m]))  → 期望下降
#    kubectl -n longhorn-system get pods -l app=csi-provisioner ... restartCount 不再增长
```

### 方案 B：升级 Longhorn 到 ≥ v1.11.3
- **原理**：官方在 v1.12.0 修复并 backport 到 v1.11.3（[#13116](https://github.com/longhorn/longhorn/issues/13116)）：由 longhorn-manager 自己在 dynamiclistener 启动前预创建 static 的 `longhorn-webhook-{ca,tls}`，并增加一个 leader-elected、6 小时 tick 的轮转 worker 负责续期。
- **风险**：当前是 **v1.7.2**，跨 4 个大版本。官方要求逐版本升级（1.7→1.8→…→1.11），离线环境需搬运大量新镜像，数据面/CRD 有多处不兼容变更，风险与工作量都高。
- **回滚**：复杂（CRD/CR 版本难以回退）
- **需重启组件**：是（全量）
- **结论**：**超出本次范围**，且你已明确要求不升级版本。仅作为长期建议记录。

### 方案 C：用 helm 预创建一对长期静态证书（stop-gap）
- **原理**：上游提到的替代方案——安装时就用 helm 预置一对长有效期证书并带 static 注解。本质与方案 A 相同，但把"注解"固化进 chart。
- **风险**：不覆盖续期；对已装集群需要重新 `helm upgrade`，会触发更多组件滚动；比方案 A 多一层封装，收益相同。
- **回滚**：`helm rollback`
- **需重启组件**：是

### 方案 D（不推荐，且对本问题无效）：删除 admission webhook 配置
- **为什么无效**：抖动来自 **manager pod 内部的 dynamiclistener**（它要为 webhook server 提供 TLS），只要 webhook server 还在监听，写入就不会停。删掉 `validatingwebhookconfiguration/longhorn-webhook-validator`、`mutatingwebhookconfiguration/longhorn-webhook-mutator` **不能止住 Secret 抖动**。
- **额外风险**：丢失 Longhorn CR 的校验能力（当前 `failurePolicy=Fail`、timeout=10s，14/19 条规则）。
- **结论**：不采用。

---

## 4. 推荐

**采用方案 A**（加 static 注解 + 滚动重启 longhorn-manager），理由：
1. 它是上游 issue #13012 作者给出的方案，且直接作用于根因（`IsStatic` 网关掉所有写路径），不是绕过现象
2. 改动面极小、可精确回滚（一条 `annotate ... -` 即可恢复）
3. 收益巨大：预计消除 **93% 的 apiserver 请求 / 94% 的写请求 / 该对象的全部 etcd 写入（≈86 万次/天）与 ≈1230/s 的 watch 事件**，直接缓解 CSI / cilium-operator 的 leader-election 失租
4. 代价可控：证书 1 年内到期（2027-09-29），记入运维台账即可
5. 不需要升级 Longhorn 版本（符合"不要升级组件版本"的约束）

**这个方案涉及"给 webhook 配固定证书"和重启 Longhorn 组件，按你的要求，我没有执行，等你批准。**

### 附带发现（与主问题无关但值得知道）
- Longhorn admission webhook 当前是**可用**的：`kubectl apply --dry-run=server` 创建 Volume 会被正常校验并拒绝（`invalid volume frontend specified`），`failurePolicy=Fail`、timeout=10s。但在抖动风暴期间曾观测到一次 `context deadline exceeded`（10s 超时）→ 说明风暴高峰时 webhook 调用会**偶发失败**，而 `failurePolicy=Fail` 意味着此时 Longhorn CR 写入会间歇性报错。修掉抖动后应一并消失。

---

## 5. 本次操作清单（全部只读 / 无副作用）

只读操作：
- `kubectl get/describe secret longhorn-webhook-tls、longhorn-webhook-ca`、`-o json`（含 managedFields）、resourceVersion/serial/fingerprint 采样
- `kubectl get pods/ds/lease/settings.longhorn.io/svc/endpoints/validatingwebhookconfiguration/mutatingwebhookconfiguration`
- `kubectl logs -l app=longhorn-manager`（日志频率统计）
- Prometheus `/api/v1/query`（所有数字来源）
- `openssl x509 -noout ...`（解码证书，只读 /tmp 文件）
- `kubectl apply --dry-run=server`（**dry-run，未创建任何对象**；且被 webhook 正常拒绝）

**未做任何变更**：
- 没有修改 / 删除任何 Secret、注解
- 没有改 Longhorn 任何设置、副本数、镜像、helm release
- 没有删除/修改任何 webhook 配置
- 没有重启任何组件
- 没有动 cilium / cert-manager / kube-prometheus-stack

---

## 6. 参考
- [longhorn/longhorn#13012 — \[IMPROVEMENT\] longhorn-manager pods race on webhook TLS Secret at scale](https://github.com/longhorn/longhorn/issues/13012)（根因与 static 方案来源）
- [longhorn/longhorn#13116 — \[BACKPORT\]\[v1.11.3\] 同一问题](https://github.com/longhorn/longhorn/issues/13116)
- [longhorn/longhorn#12742 — webhook server via longhorn-manager in a crash loop](https://github.com/longhorn/longhorn/discussions/12742)
- [longhorn/longhorn#10054 — Webhook servers initialization blocks longhorn-manager from running](https://github.com/longhorn/longhorn/issues/10054)
- [rancher/dynamiclistener](https://pkg.go.dev/github.com/rancher/dynamiclistener@v0.7.7-rc.1)
- 集群内相关记录：`/data1/ssdxt/etcd-disk-requirement.md`

---

# §7 附：etcd 监控盲区诊断（Prometheus 里 etcd 指标 0 series）

> 本节为**只诊断、未做任何变更**。结论：**etcd 监控从未配置成功**，不是回归。这是长期盯 etcd 健康（尤其磁盘 fsync 延迟）的关键缺口。

## 7.1 结论（一句话）
本集群的 etcd 是 **systemd 服务（不是 kubeadm 静态 pod）**，而 kube-prometheus-stack 的 etcd ServiceMonitor 依赖「发现带 `component=etcd` 标签的 **Pod/Endpoint**」。既然 etcd 没有 Pod，端点发现结果为 0 → Prometheus 一个 target 都没有 → **0 series**。同时该 SM 默认按 `scheme: http` 抓 `2381` 端口，而本集群 etcd 只监听 `2379/2380` 且强制 mTLS，即使有端点也抓不通。

## 7.2 证据链（全部实测）

**① etcd 根本没有 Pod —— 这是最根本的一条**
```
$ kubectl -n kube-system get pods -l component=etcd
No resources found in kube-system namespace.
```

**② Service 的 selector 匹配不到任何对象**
```
Service prometheus-stack-kube-prom-kube-etcd (kube-system)
  selector:            component: etcd        ← 匹配 0 个 Pod
  ports:               name=http-metrics  port=2381  targetPort=2381
  clusterIP:           None (headless)
```

**③ EndpointSlice 是空的**
```
EndpointSlice prometheus-stack-kube-prom-kube-etcd-4bmbh
  addressType: IPv4
  endpoints:   null      ← 没有任何地址
  ports:       null
```

**④ Prometheus 侧：job 存在但 0 个 target**
```
scrape config 里有 16 个 job，其中包含：
  serviceMonitor/monitoring/prometheus-stack-kube-prom-kube-etcd/0
     kubernetes_sd_configs: role=endpoints, namespaces=[kube-system]
     keep: __meta_kubernetes_service_label_app=kube-prometheus-stack-kube-etcd
     keep: __meta_kubernetes_endpoint_port_name=http-metrics
     scheme=http  metrics_path=/metrics  tls_config=None  bearer=None
active targets 里：apiserver/scheduler/controller-manager/kubelet 等都有 target，
但 "does an etcd job appear among active targets? False"  ← etcd 一个 target 都没有
```
→ 说明 ServiceMonitor **生效了**（Prometheus 配置里有这个 job），但**发现不到任何端点**，所以永远不产生样本。

**⑤ etcd 实际是 systemd 服务**
```
$ systemctl is-active etcd   → active
$ systemctl cat etcd
  # /etc/systemd/system/etcd.service
  ExecStart=/usr/local/bin/etcd
  EnvironmentFile=/etc/etcd.env
  Type=notify

$ ls /etc/kubernetes/manifests/
  kube-apiserver.yaml  kube-controller-manager.yaml  kube-scheduler.yaml  kube-vip.yaml
  ← 注意：没有 etcd.yaml（apiserver/scheduler/controller-manager 三个 SM 能采到，
     正是因为它们是静态 Pod；etcd 不是，所以采不到）
```

**⑥ 端口对不上：etcd 只有 2379/2380，没有 2381**
```
10.100.10.10 / .14 / .19   listeners on 2381 = 0   (三台都是 0)
ss 显示：
  127.0.0.1:2379, <node-ip>:2379   (client)
  <node-ip>:2380                   (peer)
/etc/etcd.env:
  ETCD_LISTEN_CLIENT_URLS=https://localhost:2379,https://10.100.10.10:2379
  ETCD_LISTEN_PEER_URLS=https://10.100.10.10:2380
  ETCD_CLIENT_CERT_AUTH=true                ← 强制客户端证书
  ETCD_CERT_FILE=/etc/ssl/etcd/ssl/server.crt
  ETCD_TRUSTED_CA_FILE=/etc/ssl/etcd/ssl/ca.crt
etcd 版本：3.7.0（其 --listen-metrics-urls 参数受支持）
```

**⑦ 就算端点存在，当前配置也抓不通（协议/证书层面）**
```
从 prometheus pod 里直接访问（无客户端证书）：
  https://10.100.10.10:2379/health → TLS error from peer (alert code 40): handshake failure
即 SM 的 scheme=http + tls_config=None 无法访问一个强制 mTLS 的 HTTPS 端口。

monitoring / kube-system 命名空间内都没有 etcd 客户端证书 Secret
（kube-prometheus-stack 的 etcd 采集需要额外的 client cert secret，本集群从未创建）
```

**⑧ 反证：带客户端证书就能拿到全部指标（说明修法可行）**
```
$ curl --cacert /etc/kubernetes/pki/etcd/ca.crt        --cert  /etc/kubernetes/pki/etcd/client.crt        --key   /etc/kubernetes/pki/etcd/client.key  https://10.100.10.10:2379/metrics
etcd_server_has_leader 1
etcd_disk_wal_fsync_duration_seconds_count 995660
etcd_mvcc_db_total_size_in_bytes 3.9145472e+07
etcd_server_proposals_committed_total 2.082454e+06
```
→ 这些正是盯 etcd 健康最需要的指标（含 fsync 延迟、db 大小、proposals、leader）。

## 7.3 影响
目前 **完全看不到 etcd 的任何指标**：`etcd_disk_wal_fsync_duration_seconds`（磁盘 fsync 延迟）、`etcd_mvcc_db_total_size_in_bytes`（db 增长）、`etcd_server_proposals_committed_total`（写入 QPS）、`etcd_server_leader_changes_seen_total`（leader 抖动）全部缺失。也就是说 `etcd-disk-requirement.md` 里关于"etcd 磁盘慢"的判断**没有 Prometheus 数据支撑**，只能靠外部手段观测。修好这条对定位 CSI/cilium-operator 的残余抖动也有直接价值。

## 7.4 修法建议（**均需先批准，本次未执行**）

**方案 ①（推荐）不动 etcd，改成「静态端点 + mTLS」采集**
1. 把控制面的客户端证书做成 Secret（monitoring 命名空间），例如 `kube-etcd-client-certs`：
   `ca.crt` ← `/etc/kubernetes/pki/etcd/ca.crt`，`etcd-client.crt` ← `.../client.crt`，`etcd-client.key` ← `.../client.key`
2. 因为 etcd 没有 Pod，Service 用 selector 永远发现不到端点 → **必须手工建一个 EndpointSlice/Endpoints 对象**，指向 `10.100.10.10:2379`、`10.100.10.14:2379`、`10.100.10.19:2379`，**端口名必须是 `http-metrics`**（SM 的 relabel 用这个名字做 keep）。
3. 改 ServiceMonitor `prometheus-stack-kube-prom-kube-etcd` 的 endpoint：`scheme: https`、`tlsConfig: {caFile, certFile, keyFile, serverName}`、`insecureSkipVerify: false`。
- **风险**：低。不重启 etcd、不碰控制面。
- **代价**：需要改 kube-prometheus-stack 的配置（ServiceMonitor）——按当前约定需要单独批准。

**方案 ② 让现有 SM 原样可用（改动最小，但要重启 etcd）**
1. 三台控制面 `/etc/etcd.env` 增加 `ETCD_LISTEN_METRICS_URLS=http://0.0.0.0:2381`，逐个（滚动）重启 etcd。
2. 手工建 Endpoints 指向 3 个 IP 的 `2381`，端口名 `http-metrics`。
- **风险**：中。要**重启 etcd**（控制面组件，需逐台滚动并观察 etcd 健康）；且把明文 metrics 端口暴露在内网（建议配合防火墙/网络策略限制来源）。
- **好处**：监控侧几乎不用改（保持 `scheme: http` + 2381，与 chart 默认一致）。

**方案 ③ 部署独立的 etcd exporter（DaemonSet/Deployment）**
- **风险**：低（不碰 etcd、不碰监控栈现有配置），但离线环境需要搬新镜像并维护额外组件。
- **适用**：如果不想改 ServiceMonitor、也不想动 etcd 时的折中。

**推荐 ①**：不动 etcd、不重启控制面，风险最低，且能立刻补齐 fsync 延迟等关键指标。
