#!/bin/bash
# 恢复租约参数（换盘后）+ 全集群组件健康审计
set -u
export KUBECONFIG=/etc/kubernetes/admin.conf
CTRLS="10.100.10.10 10.100.10.14 10.100.10.19"
CACERT=/etc/kubernetes/pki/etcd/ca.crt
CERT=/etc/kubernetes/pki/etcd/client.crt
KEY=/etc/kubernetes/pki/etcd/client.key
health() { etcdctl --cacert=$CACERT --cert=$CERT --key=$KEY --endpoints=https://$1:2379 endpoint health 2>/dev/null | grep -q "is healthy"; }

echo "############################################################"
echo "### 阶段 1/2：恢复租约参数（逐台滚动）"
echo "############################################################"
# 目标值：etcd 选举 2500ms/心跳 250ms；kube-vip 15/5/2；cm/sched 租约 15s/10s/2s
NODE=0
for ip in $CTRLS; do
  NODE=$((NODE+1))
  echo "--- 节点 $NODE/3 : $ip"
  OTHERS=$(echo $CTRLS | tr ' ' '\n' | grep -v "^$ip$" | tr '\n' ' ')
  OK=0; for o in $OTHERS; do health $o && OK=$((OK+1)); done
  [ $OK -lt 2 ] && { echo "  ⛔ 其余成员健康不足，中止"; break; }
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$ip "bash -s" -- "$ip" <<'REMOTE'
set -u
ip=$1
# 1) etcd.env：选举 10000→2500，心跳 500→250
cp -a /etc/etcd.env /etc/etcd.env.bak.$(date +%m%d-%H%M)
sed -i 's/^ETCD_ELECTION_TIMEOUT=.*/ETCD_ELECTION_TIMEOUT=2500/; s/^ETCD_HEARTBEAT_INTERVAL=.*/ETCD_HEARTBEAT_INTERVAL=250/' /etc/etcd.env
systemctl restart etcd
OK=0
for i in $(seq 1 12); do
  sleep 5
  etcdctl --cacert=/etc/kubernetes/pki/etcd/ca.crt --cert=/etc/kubernetes/pki/etcd/client.crt \
    --key=/etc/kubernetes/pki/etcd/client.key --endpoints=https://$ip:2379 endpoint health 2>/dev/null \
    | grep -q "is healthy" && { OK=1; break; }
done
[ $OK -ne 1 ] && { echo "  ❌ etcd 未恢复健康！恢复 etcd.env 备份"; B=$(ls -t /etc/etcd.env.bak.* | head -1); cp -a "$B" /etc/etcd.env; systemctl restart etcd; exit 1; }
echo "  ✅ etcd 2500/250 已生效"

# 2) kube-vip：30/20/5 → 15/5/2（python 精确改，禁 sed）
python3 - <<'PY'
import re
p = "/etc/kubernetes/manifests/kube-vip.yaml"
s = open(p).read(); o = s
for k, v in [("vip_leaseduration","15"),("vip_renewdeadline","5"),("vip_retryperiod","2")]:
    s = re.sub(r'(name:\s*%s\s*\n\s*value:\s*"?)\d+("?)' % k, r'\g<1>%s\g<2>' % v, s)
open(p,"w").write(s)
print("  kube-vip manifest 变更:", "是" if s != o else "无")
PY
# 3) controller-manager / scheduler：60/40/5 → 15/10/2
python3 - <<'PY'
import re
for p in ["/etc/kubernetes/manifests/kube-controller-manager.yaml","/etc/kubernetes/manifests/kube-scheduler.yaml"]:
    try: s = open(p).read()
    except FileNotFoundError: continue
    o = s
    s = s.replace("--leader-elect-lease-duration=60s","--leader-elect-lease-duration=15s")
    s = s.replace("--leader-elect-renew-deadline=40s","--leader-elect-renew-deadline=10s")
    s = s.replace("--leader-elect-retry-period=5s","--leader-elect-retry-period=2s")
    open(p,"w").write(s)
    print("  %s 变更: %s" % (p.split("/")[-1], "是" if s != o else "无"))
PY
echo "  等待静态 Pod 重建（45s）..."
sleep 45
echo "  --- 本节点关键 Pod:"
kubectl get pods -n kube-system -o wide 2>/dev/null | grep "$ip" | grep -E "kube-vip|kube-controller-manager|kube-scheduler|kube-apiserver" \
  | awk '{printf "    %-42s %-10s 重启=%s\n", $1, $3, $5}'
REMOTE
  echo ""
done

echo "############################################################"
echo "### 阶段 2/2：全集群组件健康审计（重点是重启大户）"
echo "############################################################"
kubectl get pods -A -o json 2>/dev/null | python3 -c '
import sys, json, datetime
d = json.load(sys.stdin)
now = datetime.datetime.now(datetime.timezone.utc)
rows = []
for p in d["items"]:
    md = p["metadata"]; st = p["status"]
    ns, name = md["namespace"], md["name"]
    total = 0; recent = 0; lastterm = None
    for cs in st.get("containerStatuses", []):
        total += cs.get("restartCount", 0)
        lt = (cs.get("lastState") or {}).get("terminated") or {}
        fin = lt.get("finishedAt")
        if fin:
            try:
                ft = datetime.datetime.fromisoformat(fin.replace("Z","+00:00"))
                hrs = (now - ft).total_seconds()/3600
                if hrs < 6: recent += 1
                if lastterm is None or ft > lastterm: lastterm = ft
            except Exception: pass
    if total > 0:
        ago = "%.1f小时前" % ((now-lastterm).total_seconds()/3600) if lastterm else "?"
        rows.append((total, recent, ns, name, st.get("phase"), ago))
rows.sort(reverse=True)
print("===== 重启次数 Top（累计 / 近6小时内是否有重启）=====")
for total, recent, ns, name, phase, ago in rows[:20]:
    flag = "🔴仍在崩" if recent else ("🟡6h内崩过" if recent==0 and "小时前" in ago and float(ago.split("小时")[0])<24 else "🟢稳定")
    print("  %-14s %-44s 累计=%-4d %s [%s]" % (ns, name, total, flag, ago))
print("")
print("===== 非 Running Pod =====")
bad = [(p["metadata"]["namespace"], p["metadata"]["name"], p["status"]["phase"]) for p in d["items"] if p["status"]["phase"] != "Running" and p["status"]["phase"] != "Succeeded"]
if not bad: print("  无")
for ns, name, ph in bad: print("  %s/%s = %s" % (ns, name, ph))
'
echo ""
echo "===== Deployment 副本不齐 ====="
kubectl get deploy -A --no-headers 2>/dev/null | awk '$2 != $4 {print "  "$1"/"$2" 期望"$2" 就绪"$4}' | grep -v "^$" || echo "  全部副本齐 ✓"
echo ""
echo "===== 当前告警 ====="
kubectl -n monitoring exec alertmanager-prometheus-stack-kube-prom-alertmanager-0 -c alertmanager -- \
  wget -qO- 'http://localhost:9093/api/v2/alerts?active=true&silenced=false' 2>/dev/null | python3 -c '
import sys, json
from collections import Counter
d = json.load(sys.stdin)
c = Counter((a["labels"].get("severity"), a["labels"].get("alertname")) for a in d)
for (sev, name), n in sorted(c.items()): print("  [%s] %s x%d" % (sev, name, n))
'