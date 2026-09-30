#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== 1. Grafana 看板数量（按标签统计）==="
kubectl get cm -n monitoring -l grafana_dashboard=1 --no-headers 2>/dev/null | wc -l | xargs -I{} echo "  自带看板 ConfigMap: {} 个"
kubectl get cm -n monitoring -l grafana_dashboard=1 --no-headers 2>/dev/null | awk '{print "   "$1}' | head -8
echo ""
echo "=== 2. 内置告警规则数量 ==="
kubectl get prometheusrule -n monitoring --no-headers 2>/dev/null | wc -l | xargs -I{} echo "  PrometheusRule: {} 个"
kubectl get prometheusrules -A -o json 2>/dev/null | python3 -c '
import sys,json
try: d=json.load(sys.stdin)
except Exception: print("  统计失败"); raise SystemExit
n=0
for r in d["items"]:
    for g in r["spec"].get("groups",[]): n+=len(g.get("rules",[]))
print("  告警/记录规则总条数:", n)
'
echo ""
echo "=== 3. Alertmanager 接收器配置（告警发去哪）==="
kubectl get secret alertmanager-prometheus-stack-kube-prom-alertmanager-generated -n monitoring -o jsonpath='{.data.alertmanager\.yaml}' 2>/dev/null | base64 -d 2>/dev/null | head -20
echo ""
echo "=== 4. metrics-server 镜像是否已在 Harbor ==="
curl -sk -u admin:<HARBOR_PASSWORD> 'https://harbor.wuxing.local/v2/_catalog?n=500' 2>/dev/null | python3 -c 'import sys,json; r=json.load(sys.stdin).get("repositories",[]); m=[x for x in r if "metric" in x.lower()]; print("  Harbor 里的 metrics 相关仓库:", m if m else "无（需要先搬镜像）")'
echo ""
echo "=== 5. Prometheus 数据保留与存储 ==="
kubectl get prometheus -n monitoring -o jsonpath='{.items[0].spec.retention} {.items[0].spec.storage}' 2>/dev/null; echo
kubectl get pvc -n monitoring --no-headers 2>/dev/null | head -5 || echo "  无 PVC（用的是 emptyDir，重启会丢历史数据）"