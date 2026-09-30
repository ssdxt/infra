#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== 1. kubectl top 现状 ==="
kubectl top nodes 2>&1 | head -3
echo "--- metrics-server 是否存在"
kubectl get deploy -A 2>/dev/null | grep -i metrics || echo "  没有 metrics-server"
kubectl get apiservice 2>/dev/null | grep -i metrics || echo "  没有 metrics.k8s.io API"
echo ""
echo "=== 2. monitoring 命名空间的 Service（访问入口）==="
kubectl get svc -n monitoring --no-headers 2>&1 | awk '{print "  " $1, $2, $3, $5}'
echo ""
echo "=== 3. Grafana 登录凭据 ==="
echo -n "  用户名: admin"
echo -n "  密码: "
kubectl get secret prometheus-stack-grafana -n monitoring -o jsonpath='{.data.admin-password}' 2>/dev/null | base64 -d 2>/dev/null || echo "(secret 未找到)"
echo ""
echo -n "  secret 里的 user 键: "
kubectl get secret prometheus-stack-grafana -n monitoring -o jsonpath='{.data.admin-user}' 2>/dev/null | base64 -d 2>/dev/null; echo
echo ""
echo "=== 4. Grafana 实际配置的 admin 密码来源 ==="
kubectl get deploy prometheus-stack-grafana -n monitoring -o jsonpath='{.spec.template.spec.containers[0].env}' 2>/dev/null | python3 -c 'import sys,json; [print("  ", e.get("name"), "=", (e.get("value") or e.get("valueFrom"))) for e in json.load(sys.stdin)]' 2>/dev/null | head -8
echo ""
echo "=== 5. Prometheus 抓取目标数（看有没有真的在采集）==="
kubectl exec -n monitoring prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- \
  wget -qO- 'http://localhost:9090/api/v1/targets?state=active' 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)
    t=d["data"]["activeTargets"]
    up=[x for x in t if x["health"]=="up"]
    down=[x for x in t if x["health"]!="up"]
    print("  活跃目标:", len(t), "| up:", len(up), "| 异常:", len(down))
    for x in down[:5]: print("    异常:", x["labels"].get("job"), x.get("lastError","")[:60])
except Exception as e: print("  查询失败:", e)
'
echo ""
echo "=== 6. 已安装的 Grafana 仪表盘数量 ==="
kubectl exec -n monitoring prometheus-stack-grafana-$(kubectl get pods -n monitoring -l app.kubernetes.io/name=grafana -o jsonpath='{.items[0].metadata.name}' | sed 's/prometheus-stack-grafana-//') -c grafana -- ls /var/lib/grafana/dashboards 2>/dev/null | head -5
kubectl get cm -n monitoring --no-headers 2>/dev/null | grep -c dashboard | xargs -I{} echo "  dashboard ConfigMap 数: {}"