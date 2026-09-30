# 20 — 系统层调整（chrony / etcd 参数 / journald / kube-vip 租约 / 补全 / 代理清理）

> 均为节点级（非 K8s API）改动。除 §2 涉及 etcd 逐台滚动外，其余幂等可重复执行。
> 脚本资产：`/data1/ssdxt/storage/06-fix-chrony-ntp.sh`（chrony）、
> `/data1/ssdxt/storage/05-etcd-migrate-to-fastdisk.sh`（换盘后恢复参数用其 `restore-timers`）。

---

## §1 chrony 时钟同步修复

**【原有功能】** 节点系统自带 chrony，出厂配置指向 `cn.pool.ntp.org`（外网 NPT 池）。

**【后补调整】**

- **改前现象**：`chronyc tracking` 显示 9 个节点未同步（Reference ID = 00000000），
  节点间偏差 0.9~1.4 秒——足以让证书校验、租约判断出鬼。
- **原因**：① 离线环境 `cn.pool.ntp.org` DNS 解析不了；② 8 台节点的
  `/var/lib/chrony/chrony.drift` 漂移文件损坏（含 `1000000 ppm` 坏值），chrony 反复校准失败。
- **方案**：control-02（10.100.10.14，它有一条实测可达的外部源 `5.79.108.34`）做**内网 NTP
  服务器**（`allow 10.100.10.0/24` + `local stratum 10` 兜底），其余 10 台 `server 10.100.10.14 iburst`，
  同时删掉损坏的 drift 文件。
- **精确改法**：一条脚本全搞定（幂等，Python 改写配置避免 sed 转义坑，见 90-踩坑 §7）：
  ```bash
  # 在 control-01 执行
  bash /data1/ssdxt/storage/06-fix-chrony-ntp.sh
  ```
  脚本逻辑：.14 上写入 `server 5.79.108.34 iburst` / `server cn.pool.ntp.org iburst` /
  `allow 10.100.10.0/24` / `local stratum 10`；其余 10 台把所有 `server/pool` 行替换为
  `server 10.100.10.14 iburst`，若 drift 文件含 `1000000` 则删除；逐台 `systemctl restart chronyd`。
- **验证**（脚本步骤 3 自动做，等 90 秒收敛）：
  ```bash
  chronyc sources          # 期望出现 ^* （被选中源）
  chronyc tracking | grep -E 'Reference ID|System time'
  # Reference ID 应为 0A64640E（10.100.10.14 的十六进制）；System time offset < 0.1s
  # Prometheus 侧：
  node_timex_sync_status   # 期望 11 台全部 =1
  ```
- **回滚**：恢复 `/etc/chrony/chrony.conf.bak2.<时间戳>` 并 `systemctl restart chronyd`。

---

## §2 etcd.env 参数调整（选举 10000ms / 心跳 500ms）

**【原有功能】** kk 安装的 etcd 默认 `ETCD_ELECTION_TIMEOUT=5000`、`ETCD_HEARTBEAT_INTERVAL=250`。

**【后补调整】**

- **改前现象**：`journalctl -u etcd | grep 'slow fdatasync'` 累计 1 万次（单次 1.4~3.1s）；
  raft term 涨到 150+；etcd 三台 endpoint health 时好时坏。
- **原因**：系统盘 fsync 仅 25~243 次/秒（etcd 模式实测，达标线 1000），WAL 落盘卡 →
  250ms 心跳丢失 → 反复重选。**这是慢盘的临时绕行，不是治疗。**
- **精确改法**（三台逐台滚动，每台之间必须验证健康）：
  ```bash
  for ip in 10.100.10.10 10.100.10.14 10.100.10.19; do
    ssh root@$ip 'sed -i "s/^ETCD_ELECTION_TIMEOUT=.*/ETCD_ELECTION_TIMEOUT=10000/;s/^ETCD_HEARTBEAT_INTERVAL=.*/ETCD_HEARTBEAT_INTERVAL=500/" /etc/etcd.env
  systemctl restart etcd'
    sleep 15
    ssh root@$ip 'etcdctl --cacert=/etc/kubernetes/pki/etcd/ca.crt --cert=/etc/kubernetes/pki/etcd/client.crt --key=/etc/kubernetes/pki/etcd/client.key --endpoints=https://'"$ip"':2379 endpoint health'
  done
  ```
- **验证**：
  ```bash
  grep -E 'ELECTION|HEARTBEAT' /etc/etcd.env     # 期望 10000 / 500
  journalctl -u etcd --since '1 hour ago' | grep -c 'leader changed'   # 期望 0
  ```
- **回滚**：换高性能盘并验收通过后**必须恢复** 2500/250：
  ```bash
  bash /data1/ssdxt/storage/05-etcd-migrate-to-fastdisk.sh restore-timers
  # 即把两值改回 2500/250（etcd 默认 1s 选举/100ms 心跳的 2.5s/250ms 记法）
  ```
  > 提示：换盘后恢复参数属于 README"未决事项"，别忘。

---

## §3 journald 限额 200M

**【后补调整】**

- **改前现象**：盘慢 → 组件崩溃刷日志 → 三台 control 各积 1.1G journal → 日志写盘抢 IO → 盘更慢（写放大恶性循环）。
- **精确改法**（三台 control）：
  ```bash
  for ip in 10.100.10.10 10.100.10.14 10.100.10.19; do
    ssh root@$ip 'mkdir -p /etc/systemd/journald.conf.d
  printf "[Journal]\nSystemMaxUse=200M\n" > /etc/systemd/journald.conf.d/size.conf
  journalctl --vacuum-size=200M >/dev/null 2>&1
  systemctl restart systemd-journald'
  done
  ```
- **验证**：`journalctl --disk-usage`（≤200M）；`ls /etc/systemd/journald.conf.d/size.conf`。
- **回滚**：`rm /etc/systemd/journald.conf.d/size.conf && systemctl restart systemd-journald`。

---

## §4 kube-vip 租约参数演变史（默认 5/3/1 → 60/40/10 → 回退 30/20/5，建议终值 15/5/2）

**【原有功能】** kube-vip 以静态 Pod 跑在 3 台 control，ARP 模式抢 VIP 10.100.10.250。

**【后补调整】（演变史，四个阶段）**

1. **kk 出厂（坏的）**：kk v4.0.7 模板在渲染完用户 `kube_vip.env` 后又**无条件追加**硬编码
   `vip_leaderelection=true / vip_leaseduration=5 / vip_renewdeadline=3 / vip_retryperiod=1`。
   env 后出现的键生效 → 用户配置永远被 5/3/1 覆盖 → 慢盘下 5s 租约必丢 →
   `level=fatal msg="lost leadership"` → VIP 闪断、`create cluster` 卡死在 CoreDNS 步骤。
2. **去重修正（必做）**：Python 去重保留**用户配置的首次出现**（整对删除重复项 + 孤儿行）：
   ```bash
   for ip in 10.100.10.10 10.100.10.14 10.100.10.19; do
     ssh root@$ip "python3 -" <<'PYEOF'
   keys = ('vip_leaseduration', 'vip_renewdeadline', 'vip_retryperiod')
   p = '/etc/kubernetes/manifests/kube-vip.yaml'
   lines = open(p).read().split(chr(10))
   out, seen, i = [], set(), 0
   while i < len(lines):
       ln = lines[i]; s = ln.strip(); nm = None
       if s.startswith('- name: '): nm = s[8:]
       if nm in keys:
           if nm in seen:            # 后续重复：孤儿行删一行，整对删两行
               i += 1
               if i < len(lines) and lines[i].strip().startswith('value:'): i += 1
               continue
           seen.add(nm)              # 首次出现（用户配置）保留
       out.append(ln); i += 1
   open(p, 'w').write(chr(10).join(out))
   print('dedup ok, kept:', len(seen))
   PYEOF
   done
   ```
   ⚠️ 早期试过 `sed` 单行删除，会留下孤儿 `name:` 行破坏 YAML，导致 kubelet 弃用静态 Pod
   （kube-vip 直接消失）——**禁用 sed**，见 90-踩坑 §6。
   ⚠️ 安装期还试过"每 5 秒去重一次"的守望者循环，与 kk 写清单竞态把清单写坏过——**禁用守望者**。
3. **放宽到 60/40/10**：慢盘绕行期把保留的用户值 30/20/5 升到 60/40/10（python 精确整对替换），
   与 scheduler/controller-manager/cilium-operator 的 60/40/5 一致，扛 40 秒级存储尖峰。
4. **后来被回退到 30/20/5**（当前实机值，2026-09-29 在 `/etc/kubernetes/manifests/kube-vip.yaml` 核实）。
5. **建议**：换高性能盘并恢复 etcd 正常参数后，把三个值改为 **15/5/2**（比默认 5/3/1 稍宽，
   比绕行值快得多），兼顾切换速度与残余抖动。
- **验证**：
  ```bash
  grep -A1 -e vip_leaseduration -e vip_renewdeadline -e vip_retryperiod \
    /etc/kubernetes/manifests/kube-vip.yaml | grep -E 'name|value'
  # 期望：每个键只出现一次；当前 30/20/5；换盘后 15/5/2
  kubectl -n kube-system get pods | grep kube-vip        # 三个 1/1 Running
  curl -k --noproxy '*' --max-time 8 https://10.100.10.250:6443/healthz   # ok
  ```
- **回滚**：静态 Pod 清单改回即自动生效；或恢复 backup 目录下同名清单。
- **提醒**：`kk create cluster` 重跑会再次渲染出重复的 5/3/1 —— 每次重跑后必须重新执行第 2 步去重。

---

## §5 kubectl / helm 补全

```bash
# 三台 control 各执行一次（bash 环境）
echo 'source <(kubectl completion bash)'  >> /root/.bashrc
echo 'source <(helm completion bash)'     >> /root/.bashrc
echo 'alias k=kubectl'                    >> /root/.bashrc
echo 'complete -o default -F __start_kubectl k' >> /root/.bashrc
source /root/.bashrc
```
验证：新开 shell 输 `kubectl get po<TAB>` 能补全即成。回滚：删对应行即可。

---

## §6 清理节点上的 http_proxy 环境变量

**【后补调整】**

- **改前现象**：kube-proxy/静态 Pod 的 env 里被烘进 `HTTPS_PROXY` 等变量，组件连 VIP 6443
  报 `Access violation`（tinyproxy 拒绝页）。
- **原因**：首次跑 `kk create cluster` 的 shell 带着代理变量，kk 把环境写进了 Pod spec；
  且 `NO_PROXY` 不含 VIP。
- **预防（重装前必做）**——11 台节点彻底清掉：
  ```bash
  for ip in 10.100.10.{10,14,19,33,34,39,41,44,45,46,47}; do
    ssh root@$ip 'sed -i "/^http_proxy=/d;/^https_proxy=/d;/^HTTP_PROXY=/d;/^HTTPS_PROXY=/d;/^no_proxy=/d;/^NO_PROXY=/d" /etc/environment; rm -f /etc/profile.d/zz-proxy.sh'
  done
  ```
  跑 kk 的 shell 里再 `unset` 一遍并 `env | grep -i proxy` 确认为空。
  原则：**内网集群默认直连，代理只做例外**（apt 出网走 `/etc/apt/apt.conf.d/99proxy`，与 shell 环境无关）。
- **装后修**（若已中招）：
  ```bash
  export KUBECONFIG=/etc/kubernetes/admin.conf
  kubectl set env ds/kube-proxy -n kube-system HTTPS_PROXY- HTTP_PROXY- NO_PROXY- http_proxy- https_proxy- no_proxy-
  # 静态 Pod 清单用 python 删代理 env 块（kubelet 检测变化自动重启）：
  for ip in 10.100.10.10 10.100.10.14 10.100.10.19; do
    ssh root@$ip "python3 -" <<'EOF'
  import glob
  for f in glob.glob('/etc/kubernetes/manifests/*.yaml'):
      lines = open(f).read().split('\n')
      out, skip = [], False
      for ln in lines:
          if '- name:' in ln and 'proxy' in ln.lower():
              skip = True; continue
          if skip:
              if ln.strip().startswith('value:'): continue
              skip = False
          out.append(ln)
      if len(out) != len(lines):
          open(f, 'w').write('\n'.join(out)); print('cleaned', f)
  EOF
  done
  ```
- **验证**：
  ```bash
  kubectl get pod -n kube-system kube-apiserver-wxq-control-01 -o jsonpath='{.spec.containers[0].env}'
  # 期望：无 PROXY 相关键
  ```
- **回滚**：不需要（回滚 = 重新引入故障）。

---

## §7 断点续跑：kubelet 预检死锁（重跑 create cluster 之前）

**【后补调整】**

- **现象**：中断后重跑 `kk create cluster`，30 秒内死：
  `The kubelet service must be running and active when it is loaded.`
- **原因**：kk 先 enable kubelet 不 start，join 时才拉起；中断重跑时 10 台非安装节点的
  kubelet 处于 loaded-but-not-active，预检直接判死。
- **精确改法**（守卫版，只清非 active 的节点，活的绝不碰；**绝不能清 control-01**，
  否则 kk 误判未初始化会重跑 kubeadm init 报端口冲突——实际踩过）：
  ```bash
  for ip in 10.100.10.14 10.100.10.19 10.100.10.33 10.100.10.34 10.100.10.39 \
            10.100.10.41 10.100.10.44 10.100.10.45 10.100.10.46 10.100.10.47; do
    ssh root@$ip 'if ! systemctl is-active --quiet kubelet 2>/dev/null; then
      systemctl stop kubelet 2>/dev/null; rm -f /etc/systemd/system/kubelet.service
      rm -rf /etc/systemd/system/kubelet.service.d; systemctl daemon-reload
    fi'
  done
  ```
- **验证**：重跑 create cluster 能通过预检；kk 死在 CoreDNS 时手动补
  `kubectl apply -f /etc/kubernetes/coredns.yaml` 后再重跑。
- **回滚**：无（kubelet 单元由 kk 重新部署）。

---

## §8 镜像 GC 与磁盘治理（imageGC 70/60 + 每周 prune 兜底）

> 2026-09-30 落地（11 台）。脚本：`/data1/ssdxt/storage/07-kubelet-imagegc-tune.sh`（逐台执行，失败自动回滚）。
> 背景：worker 根盘 48G 曾用 71~78%（/var/lib/containerd 镜像 25G+，Longhorn 升级一次拉了 71 个镜像）。

**【原有功能】** kubelet 自带镜像垃圾回收：根盘使用率超过 `imageGCHighThresholdPercent` 时
持续删未使用镜像，直到降到 `imageGCLowThresholdPercent` 以下。kk 出厂的
`/var/lib/kubelet/config.yaml` 里**没有**这两个键 → kubelet 用默认 85/80 → 48G 的小根盘到
85% 才开始清（≈41G，镜像 25G+ 时基本等于等死）。

**【后补调整】**

- **改前现象**：worker 根盘 71~78%，距离默认 GC 阈值 85% 只差 7~14 个百分点；再拉一次大版本镜像就可能打满。
- **精确改法**（每台，逐台执行）：
  ```bash
  # 备份 → PyYAML 写入两个键 → 重启 kubelet → 验证（kubelet active / 节点 Ready / Pod 零异常）
  # 失败自动恢复 .bak.gc.<日期> 并重启 kubelet。执行记录见脚本输出。
  scp root@10.100.10.10:/data1/ssdxt/storage/07-kubelet-imagegc-tune.sh root@<节点IP>:/data1/ssdxt/storage/
  ssh root@<节点IP> 'bash /data1/ssdxt/storage/07-kubelet-imagegc-tune.sh <节点名> <节点IP>'
  ```
  修改内容（/var/lib/kubelet/config.yaml 新增两个顶层键）：
  ```yaml
  imageGCHighThresholdPercent: 70
  imageGCLowThresholdPercent: 60
  ```
  另每台装每周兜底 cron `/etc/cron.d/wxq-image-prune`（每周日 03:30）：
  ```
  30 3 * * 0 root crictl rmi --prune >> /var/log/wxq-image-prune.log 2>&1
  ```
- **containerd GC 与 kubelet GC 的区别**（为什么两个都要管）：
  - kubelet GC（本节配的）：**磁盘水位驱动**，看根盘使用率，删"没有容器引用的镜像"，
    兜的是"盘快满了"这种系统性风险；阈值是百分比。
  - containerd 自身 GC：**引用计数驱动**，快照/内容存储只在内部对象失去引用时回收空间，
    不看磁盘水位——"盘满了但对象都有引用"时 containerd 不会动手，必须靠 kubelet GC 或 `crictl rmi --prune`。
  - `crictl rmi --prune`：删除所有**未被任何容器引用**的镜像，与 kubelet GC 删的东西同类，
    不碰运行中容器——安全的兜底。
- **验证**：
  ```bash
  grep imageGC /var/lib/kubelet/config.yaml          # 期望 70 / 60 两行
  systemctl is-active kubelet && kubectl get nodes   # 11/11 Ready
  ls /etc/cron.d/wxq-image-prune                     # cron 在位
  ```
- **回滚**：`cp /var/lib/kubelet/config.yaml.bak.gc.<日期> /var/lib/kubelet/config.yaml && systemctl restart kubelet`；cron 回滚 `rm /etc/cron.d/wxq-image-prune`。

### 执行前后对照（2026-09-30 实测）

| 节点 | IP | 根盘前 | 根盘后 | 镜像数前→后 | kubelet | Pod |
|---|---|---|---|---|---|---|
| wxq-control-01 | .10 | 40% | 40% | 20→20 | active | 正常 |
| wxq-control-02 | .14 | 37% | 37% | 19→19 | active | 正常 |
| wxq-control-03 | .19 | 37% | 37% | 18→18 | active | 正常 |
| wxq-run-01 | .33 | 37% | 37% | 20→20 | active | 正常 |
| wxq-run-02 | .34 | 38% | 38% | 22→22 | active | 正常 |
| wxq-run-03 | .39 | 36% | 36% | 24→24 | active | 正常 |
| wxq-run-04 | .41 | 36% | 36% | 23→23 | active | 正常 |
| wxq-run-05 | .44 | 35% | 35% | 19→19 | active | 正常 |
| wxq-run-06 | .45 | 36% | 36% | 21→21 | active | 正常 |
| wxq-run-07 | .46 | 35% | 35% | 19→19 | active | 正常 |
| wxq-run-08 | .47 | 22% | 22% | 24→24 | active | 正常 |

> 执行时磁盘已回落到 35~40%（低于低水位 60%），GC 未触发清理、镜像数不变——**本次是预防性配置**：
> 下次根盘冲上 70% 时 kubelet 会自动清到 60%，不再依赖人工。全程零 Pod 异常。
> （.33 首跑因脚本在 worker 上找不到 admin.conf 误判回滚一次，修正脚本后重跑成功，配置无损。）

### 衍生：containerd 目录迁 /data1（方案，未执行）

若镜像量仍挤压根盘，可把 containerd root 迁到 931G 的 /data1 —— 完整方案（与 Longhorn 共盘影响分析、
三条规矩、回滚）见 [08-containerd迁移data1方案.md](08-containerd迁移data1方案.md)，
脚本 `/data1/ssdxt/storage/08-containerd-relocate.sh`。⚠️ 迁移后 kubelet imageGC 对新目录**失效**，磁盘保护移交巡检 cron。

---

## §9 kubelet 系统资源预留（systemReserved / kubeReserved，11 台）

**【原有功能】** kubelet 原生资源预留机制：`systemReserved`（系统进程）、`kubeReserved`（K8s 组件），
预留部分从 Node allocatable 中扣除，防止系统进程被业务 Pod 饿死。

**【后补调整】**（2026-09-30，11 台全部落地）

- **改前现象**：原配置只有 `systemReserved: cpu 200m / memory 250Mi` + `kubeReserved: cpu 200m / memory 250Mi`，
  无 ephemeral-storage 预留；节点业务 Pod 可消耗至仅剩 400m/500Mi 之外的全部资源，系统进程无兜底。
- **精确改法**（逐台执行，每台成功后再下一台；脚本幂等，自动备份 `.bak.日期`，kubelet 起不来自动回滚）：
  ```bash
  # 脚本双份落地：/data1/ssdxt/tools/kubelet-reserve.sh（scp 到目标机 /root/kr.sh 执行）
  bash /root/kr.sh
  ```
  合并后的目标值（PyYAML 合并，已有键更新、缺键插入）：
  ```yaml
  systemReserved: {cpu: 300m, memory: 500Mi}
  kubeReserved: {cpu: 300m, memory: 500Mi, ephemeral-storage: 5Gi}
  ```
  每台流程：备份 → python 合并 → `systemctl restart kubelet` → `is-active` + healthz(10248) 检查 →
  kubectl 确认 allocatable 变小 / Ready / 全集群 Pod 无异常 / longhorn-system 无新增异常。
- **验证**（allocatable 前后对照，2026-09-30 实测）：

| 节点 | allocatable CPU 前→后 | allocatable MEM 前→后 |
|---|---|---|
| wxq-control-01 | 3600m → 3400m | 7382540897 → 6858252897 |
| wxq-control-02 | 3600m → 3400m | 7382544788 → 6858256788 |
| wxq-control-03 | 3600m → 3400m | 7382544788 → 6858256788 |
| wxq-run-01 | 31600m → 31400m | 127785771113 → 127261483113 |
| wxq-run-02 | 31600m → 31400m | 127785767221 → 127261479221 |
| wxq-run-03 | 31600m → 31400m | 127785767221 → 127261479221 |
| wxq-run-04 | 31600m → 31400m | 127785759439 → 127261471439 |
| wxq-run-05 | 31600m → 31400m | 127785763330 → 127261475330 |
| wxq-run-06 | 31600m → 31400m | 127785778895 → 127261490895 |
| wxq-run-07 | 31600m → 31400m | 127785755548 → 127261467548 |
| wxq-run-08 | 31600m → 31400m | 127785763330 → 127261475330 |

  即每台 CPU -200m、MEM -~500Mi（原 400m/500Mi → 新 600m/1000Mi + ephemeral-storage 5Gi）。
  全程 11/11 kubelet active、healthz=200、节点 Ready、零 Pod 重启异常。
  ⚠️ 当日 Longhorn 升级滚动中：每台做完均确认 longhorn-system Pod 全 Running 再继续（期间两次
  ContainerCreating 为另一侧升级滚动所致，与本操作无关，已确认恢复）。
- **回滚**：`cp /var/lib/kubelet/config.yaml.bak.<日期> /var/lib/kubelet/config.yaml && systemctl restart kubelet`。

---

## §10 APT 自动更新管控（11 台）

**【原有功能】** Ubuntu 22.04 自带 `unattended-upgrades`（服务默认 active，20auto-upgrades 存在）。

**【后补调整】**（2026-09-30）

- **改前现象**：`apt-mark showhold` 显示各台已 hold 内核 5.15.0-125 全套
  （linux-headers/-generic、linux-image、linux-modules/-extra 共 5 个包，与台账一致✅）；
  但 unattended-upgrades 活跃且未显式禁自动重启。
- **精确改法**（幂等脚本 `/data1/ssdxt/tools/apt-hardening.sh`，scp 到目标机执行）：
  1. `/etc/apt/apt.conf.d/20auto-upgrades` 确保存在：`Update-Package-Lists "1"; Unattended-Upgrade "1";`
     （保留安全补丁自动下载安装，只关危险行为）。
  2. 新建 `/etc/apt/apt.conf.d/52wxq-hardening`：
     ```conf
     Unattended-Upgrade::Automatic-Reboot "false";
     Unattended-Upgrade::Automatic-Reboot-Time "03:00";
     Unattended-Upgrade::Remove-Unused-Dependencies "false";
     ```
  3. 内核未 hold 时补 `apt-mark hold linux-image-generic`（本次各台原本只有版本化 hold，
     补了 meta 包 hold；版本化 5 包保持不动）。
- **验证**：11 台 `apt-config dump | grep Automatic-Reboot` → `"false"`；hold 列表各台 6 项（5 项内核版本化 + linux-image-generic）。
- **回滚**：`rm /etc/apt/apt.conf.d/52wxq-hardening`；`apt-mark unhold linux-image-generic`。

---

## §11 etcd systemd OOM 保护（3 台 control）

**【原有功能】** systemd `OOMScoreAdjust=` 直接设置 etcd 进程的 `/proc/<pid>/oom_score_adj`。

**【后补调整】**（2026-09-30 核查）

- **现状核查**：三台 `/etc/systemd/system/etcd.service` 的 `[Service]` 段**已存在 `OOMScoreAdjust=-1000`**
  （优于本次目标值 -999），`/proc/$(pgrep etcd)/oom_score_adj` 实测三台均为 `-1000`。
- **结论**：**未做任何改动**（目标 -999 已被 -1000 覆盖，改低反而削弱保护）。etcd.service 内容见
  `/etc/systemd/system/etcd.service`（只读 444 权限）。
- **若新环境复刻**：确认 `[Service]` 段含 `OOMScoreAdjust=-1000`，否则备份后插入并
  `systemctl daemon-reload && systemctl restart etcd`（逐台滚动 + endpoint health 验证，同 §2 流程）。

---

