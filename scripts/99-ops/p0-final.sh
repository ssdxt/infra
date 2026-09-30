#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "== 恢复 coredns（server-side + force-conflicts）=="
ls -la /tmp/coredns-restore.json 2>/dev/null || { echo "restore 文件不存在，重建"; }
python3 - <<'PY'
import json, subprocess
def k(*a): return subprocess.run(["kubectl",*a],capture_output=True,text=True,encoding="utf-8",errors="replace")
ORIGINAL = """.:53 {
  cache 30
  errors
  ready
  prometheus :9153
  loop
  reload
  loadbalance

  health {
    lameduck 5s
  }
  kubernetes cluster.local in-addr.arpa ip6.arpa {
    pods insecure
    fallthrough in-addr.arpa ip6.arpa
    ttl 30
  }
  forward . /etc/resolv.conf {
    max_concurrent 1000
  }
}
"""
cur = json.loads(k("get","cm","coredns","-n","kube-system","-o","json").stdout)
cur["data"]["Corefile"] = ORIGINAL
json.dump(cur, open("/tmp/coredns-restore.json","w"), ensure_ascii=False)
r = k("apply","--server-side","--force-conflicts","-f","/tmp/coredns-restore.json")
print("  apply:", (r.stdout or r.stderr).strip())
k("rollout","restart","deploy/coredns","-n","kube-system")
subprocess.run(["kubectl","-n","kube-system","rollout","status","deploy/coredns","--timeout=180s"],
               capture_output=True, text=True)
print("  rollout:", subprocess.run(["kubectl","-n","kube-system","rollout","status","deploy/coredns"],
      capture_output=True, text=True).stdout.strip())
PY
sleep 20
echo "== 集群内部 DNS 复测 =="
kubectl run dv5 -n default --rm -i --restart=Never --image=harbor.wuxing.local/library/nginx:1.27-alpine \
  -- nslookup kubernetes.default.svc.cluster.local 2>&1 | tail -3
echo "== Loki 连通 =="
kubectl -n logging exec loki-0 -c loki -- wget -q -O- -T 5 http://loki-0.logging.svc.cluster.local:3100/ready 2>&1 | head -c 40
echo ""
echo "== 当前告警 =="
kubectl -n monitoring exec alertmanager-prometheus-stack-kube-prom-alertmanager-0 -c alertmanager -- \
  wget -qO- "http://localhost:9093/api/v2/alerts?active=true" 2>/dev/null | grep -oE '"alertname":"[^"]*"' | sort | uniq -c