# 90 — 踩坑与修复记录

> 每条：现象 → 根因 → 修复 → 验证。跨章主题只留索引，细节在对应章节。

---

## §1 PowerShell 剥引号问题与 `.x.sh` 模式（Windows 侧工具坑）

- **现象**：在 PowerShell 5.1 里 `ssh root@IP "python3 -c 'print(\"a b\")'"` 一类复杂远程命令，
  远端收到的命令**所有双引号被剥掉**，逻辑全乱；偶尔还能"看起来跑通但结果错"。
- **根因**：PowerShell 5.1 对传给 ssh 的远程命令参数做引号重组，双引号在多层转义中丢失。
- **修复（固定模式，所有复杂远程操作照抄）**：
  1. 本地写 `x.sh` / `x.py`（**必须 LF 换行**，CRLF 会让 bash/python 报错）；
  2. `scp -O C:\path\x.sh root@IP:/tmp/x.sh`；
  3. `ssh root@IP 'bash /tmp/x.sh'`（单引号内只有一层，安全）。
  SSH 认证走 askpass：
  ```powershell
  $env:SSH_ASKPASS='C:\Users\CC\Desktop\dsh\askpass.cmd'
  $env:SSH_ASKPASS_REQUIRE='force'; $env:DISPLAY='localhost:0'
  ssh root@10.100.10.10
  ```
- **验证**：远端 `cat -A /tmp/x.sh | head -2` 确认无 `^M$`。
- 关联：90-§6（sed 孤儿行）同属"别把复杂逻辑塞进一行远程命令"。

---

## §2 代理变量被烘进 Pod 清单（`Access violation`）

- **现象**：装完 kube-proxy 全起但 ClusterIP 不通；kubectl 走 VIP 报
  `Get "https://10.100.10.250:6443/...": Access violation`（tinyproxy 拒绝页）。
- **根因**：跑 `kk create cluster` 的 shell 带代理变量，kk 把 HTTP(S)_PROXY/no_proxy 烘进
  静态 Pod 清单与 DaemonSet；no_proxy 不含 VIP。
- **修复**：预防（装前 11 台清 /etc/environment + shell unset）与装后修（`kubectl set env ... X-`
  + python 清静态清单），命令全文在 **20-系统层 §6**。
- **验证**：`kubectl get pod kube-apiserver-wxq-control-01 -n kube-system -o jsonpath='{.spec.containers[0].env}'` 无 PROXY 键。

---

## §3 skopeo 单架构复刻改变摘要 → `@sha256:` 引用 404（fix-chart-images.py 的用途与局限）

- **现象**：Pod 全家 `Failed to pull "...@sha256:ae9ea21f...": not found`（Harbor 里确实有镜像）。
- **根因**：上游镜像是**多架构 manifest list**，chart values 里常带 `@sha256:` 摘要引用；
  我们用 `skopeo copy --override-arch amd64` 只搬单架构 → **digest 必然变化** → 摘要引用永远 404。
  所以复刻军规 #3：**禁止 @sha256 引用，一律 `仓库:tag`**。
- **fix-chart-images.py 的用途**：把 chart 的 values.yaml 里所有 `repository` 键改写为 Harbor 地址
  （有 registry 字段 → `registry=域名, repository=项目/末段`；无 → `repository=域名/项目/末段`），
  自动生成离线 values。
- **局限**：① 它**只改 repository，不处理 digest**（`@sha256:` 在 manifest 里，不在 values 里）——
  运行态 digest 仍要靠 30-网络 §1 的 python 去 digest patch；② 早期版本有**双重前缀 bug**
  （`harbor.wuxing.local/harbor.wuxing.local/...`），已修（改写前判断 `'harbor' not in repo`），
  但生成后仍要人工抽查 values；③ 对"镜像名和容器名不一致"的组件无感知（localpv：镜像
  provisioner-localpv、容器 localpv-provisioner）。
- **验证**：`kubectl get ds cilium ... -o jsonpath='{...image}'` 不含 `@sha256:`；镜像拉取成功。

---

## §4 chrony drift 文件损坏（1000000 ppm）

- **现象**：9 节点 `chronyc tracking` 未同步，偏差 0.9~1.4s；修完 server 指向后仍有个别节点不收敛。
- **根因**：`/var/lib/chrony/chrony.drift` 含坏值 `1000000`（ppm），chrony 用它做频率补偿越修越偏。
- **修复**：`06-fix-chrony-ntp.sh` 里检测 drift 内容含 `1000000` 即删除（chrony 会重新学习）；
  全套方案见 **20-系统层 §1**。
- **验证**：`chronyc sources` 出现 `^*`；`node_timex_sync_status` 全 1。

---

## §5 etcd 监控 0 序列根因（systemd vs 静态 Pod）

- **现象**：Prometheus 查 etcd 任何指标 0 series；ServiceMonitor 存在但 0 target。
- **根因**：kk 装的 etcd 是 **systemd 服务**（`/etc/systemd/system/etcd.service`），
  无 Pod → selector `component=etcd` 匹配 0 端点；且 SM 默认 http:2381，本集群 etcd 是
  mTLS:2379 —— 双重不通。证据链与方案 ①（静态 Endpoints + mTLS，待批）见 **50-监控 §4**。
- **教训**：控制面组件的监控方案必须先确认组件形态（systemd/静态 Pod/Deployment），
  不能假设 kubeadm 标准布局。

---

## §6 kube-vip 被 kk 回退参数（模板重复渲染）+ sed 孤儿行

- **现象**：`create cluster` 卡死 CoreDNS 步骤 `dial tcp 10.100.10.250:6443: no route to host`，
  VIP 闪断；修一次好一阵又坏。
- **根因（两个叠加）**：① kk v4.0.7 模板在用户 `kube_vip.env` 之后**无条件追加**硬编码
  `vip_leaseduration=5/renewdeadline=3/retryperiod=1`（env 后键生效 → 用户值被覆盖）；
  ② 每次重跑 create cluster 都重新渲染，修正被冲掉。
- **修复**：python 去重（保留首次出现）+ 每次重跑后重做；演变史与脚本全文见 **20-系统层 §4**。
- **血泪**：用 `sed '/name: vip_leaseduration/{n;/value: "5"/d}'` 单行删除会**留下孤儿 name 行**
  破坏 YAML → kubelet 弃用静态 Pod、kube-vip 直接消失；"每 5 秒去重"的守望者循环与 kk 写清单
  竞态，把清单写坏过一次。**结论：静态 Pod 清单只允许 python 整对操作，禁 sed、禁守望者。**

---

## §7 plant01 docker-compose 丢失与重建

- **现象**：plant01（10.100.10.29）上的 Harbor/Prometheus/VictoriaMetrics 容器编排配置一度丢失，
  组件无法凭配置重建。
- **修复**：docker-compose.yaml 已重建（现文件在 plant01 本机），remote_write 接收端依赖其上的
  Prometheus `--web.enable-remote-write-receiver` 与 `retention.size=25GB`（见 50-监控 §2）。
- **教训**：plant01 虽是"平台机"也要纳入配置备份（至少 docker-compose 与 /etc/exports 定期
  备到 /data1/ssdxt）；否则 50 章 remote_write、Harbor 通道全部单点。

---

## §8 sed 改配置不生效 → 改用 Python 精确改写

- **现象**：`sed -i 's/.../.../'` 改 chrony/静态清单类配置后，有的没改上、有的改坏（孤儿行、
  转义丢失、多行结构破坏）。
- **根因**：sed 对多行/成对结构（YAML `name:`+`value:`、含特殊字符的 URL）天然脆弱；
  转义地狱（密码 `<HARBOR_PASSWORD>`、引号嵌套）。
- **修复（纪律）**：凡改**结构化配置**（YAML/conf 多行块），一律用 python 按行状态机处理 +
  自动备份 `.bak.<时间戳>`（范本：`06-fix-chrony-ntp.sh` 内嵌的 fix_chrony_client.py、
  20-系统层 §4 的去重脚本）。sed 只用于**单行精确匹配**（如 etcd.env 的 KEY=VALUE）。

---

## §9 Alertmanager 删规则不发 resolved 通知

- **现象**：下线/删除某条告警规则后，已触发实例永远收不到 resolved 通知，告警列表残留。
- **根因**：Alertmanager 的 resolved 通知只对"仍然匹配到规则的活跃 alert"计算；规则删掉后
  Prometheus 不再发送该 series，Alertmanager 侧 alert 超时后才自动过期——期间不补发 resolved。
- **修复**：删规则的同时**手工清 Alertmanager 活跃告警**（等 `resolve_timeout`（默认 5m～1h）
  自然过期，或临时调低 / 重启 Alertmanager 清态）；文档化"删规则 ≠ 立即 resolved"。
- **验证**：Alertmanager UI 里对应 alert 进入过期/消失。

---

## §10 Admission webhook `Too long` 用 `--server-side`

- **现象**：`kubectl apply -f gateway-api/experimental-install.yaml` 报
  `metadata.annotations: Too long: may not be more than 262144 bytes`（CRD 里
  `kubectl.kubernetes.io/last-applied-configuration` 注解超限）。
- **修复**：改用 server-side apply，配置归属服务端，不再写 last-applied 注解：
  ```bash
  kubectl apply --server-side --force-conflicts -f <大 CRD 清单>
  ```
  （`--force-conflicts` 仅在字段属主冲突时需要。）
- **验证**：apply 成功；`kubectl get crd ... -o jsonpath='{.metadata.annotations}'` 无超长注解。

---

## §11 网络与存储基线劣化（排障背景知识）

- **网络**：iperf3 四方向实测 ~100Mbps（百兆级）。影响：镜像拉取、Longhorn 副本同步。
  方法与达标线见 `oneclick/iperf3使用参考.md`；RTT 正常（<1ms）→ 网卡/端口限速。
- **存储**：fio 实测 fsync 25~243/s、随机读 p99 3~17 秒、顺序读反而 150~660M/s =
  **缓存型共享存储 + 无写缓存**特征；并发测试更慢 2~3 倍 = 共享后端争抢。
  fio 方法（注意 etcd 模式 `--direct=0 --fdatasync=1`，direct=1 是假数据）见
  `oneclick/fio使用参考.md` 与 40-存储 §4。
- **判读口诀**：顺序快+随机慢=共享阵列；fsync 低=禁跑数据库；RTT 好+带宽低=端口限速。
