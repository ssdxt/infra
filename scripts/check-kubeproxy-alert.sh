#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== 1. kube-proxy 还在吗 ====="
kubectl -n kube-system get ds kube-proxy 2>&1 | head -3 | sed 's/^/  /'
echo -n "  kube-proxy Pod 数: "
kubectl -n kube-system get pods -l k8s-app=kube-proxy --no-headers 2>/dev/null | wc -l
echo -n "  Cilium KPR 是否开启: "
kubectl -n kube-system get cm cilium-config -o jsonpath='{.data.kube-proxy-replacement}' 2>/dev/null; echo
echo ""
echo "===== 2. 当前正在触发的所有告警（Alertmanager API）====="
POD=$(kubectl -n monitoring get pods -l app.kubernetes.io/name=alertmanager --no-headers 2>/dev/null | head -1 | awk '{print $1}')
echo "  Alertmanager Pod: $POD"
kubectl -n monitoring exec $POD -c alertmanager -- wget -qO- 'http://localhost:9093/api/v2/alerts' 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)
    if not d: print("  （无告警）")
    seen={}
    for a in d:
        n=a["labels"].get("alertname"); sev=a["labels"].get("severity")
        seen.setdefault((n,sev),0); seen[(n,sev)]+=1
    for (n,sev),c in sorted(seen.items()):
        print("  [%s] %s  x%d" % (sev, n, c))
except Exception as e: print("  读取失败:", e)
'
echo ""
echo "===== 3. KubeProxyDown 规则定义 ====="
kubectl -n monitoring get prometheusrule --no-headers 2>/dev/null | grep -i proxy | sed 's/^/  /'
kubectl -n monitoring get prometheusrule prometheus-stack-kube-prom-kubernetes-system-kube-proxy -o json 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)
    for g in d["spec"]["groups"]:
        print("  规则组:", g["name"])
        for r in g["rules"]:
            print("    -", r.get("alert"), "| for:", r.get("for"), "|", (r.get("expr") or "").strip()[:110])
except Exception as e: print("  读取失败:", e)
'
echo ""
echo "===== 4. 受影响的同类"组件不存在"告警还有哪些 ====="
kubectl -n monitoring get prometheusrule --no-headers 2>/dev/null | awk '{print "  "$1}'
echo ""
echo "===== 5. ServiceMonitor 里 kube-proxy 相关 ====="
kubectl -n monitoring get servicemonitor --no-headers 2>/dev/null | grep -i -E 'proxy|etcd|scheduler|controller' | sed 's/^/  /'
echo ""
echo "===== 6. Prometheus 里 kube-proxy 的 target ====="
PP=$(kubectl -n monitoring get pods -l operator.prometheus.io/name=prometheus-stack-kube-prom-prometheus --no-headers 2>/dev/null | head -1 | awk '{print $1}')
[ -z "$PP" ] && PP=$(kubectl -n monitoring get pods --no-headers 2>/dev/null | grep 'prometheus-stack-kube-prom-prometheus-0' | awk '{print $1}')
echo "  Prometheus Pod: $PP"
kubectl -n monitoring exec $PP -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/query?query=count(up)' 2>/dev/null | python3 -c '
import sys,json
d=json.load(sys.stdin); print("  count(up) =", d["data"]["result"][0]["value"][1])
' 2>/dev/null
for job in kube-proxy kube-etcd kube-scheduler kube-controller-manager; do
  echo -n "  job=$job: "
  kubectl -n monitoring exec $PP -c prometheus -- wget -qO- "http://localhost:9090/api/v1/query?query=count(up%7Bjob%3D%22$job%22%7D)" 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin); r=d["data"]["result"]
    print(r[0]["value"][1] if r else "0 (无此 job)")
except Exception: print("查询失败")
'
done
