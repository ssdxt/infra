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
