#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== logging 目录内容 ==="
ls -la /data1/ssdxt/logging/ | sed 's/^/  /'
echo ""
echo "=== 看板 ConfigMap ==="
kubectl -n logging get cm loki-dashboard -o custom-columns=NAME:.metadata.name,LABELS:.metadata.labels --no-headers 2>/dev/null | sed 's/^/  /'
echo ""
echo "=== 日志面板用的接口（query_range）实测 ==="
S=$(( $(date +%s) - 600 ))000000000
E=$(date +%s)000000000
kubectl -n logging exec loki-0 -c loki -- wget -qO- \
  "http://localhost:3100/loki/api/v1/query_range?query=%7Bnamespace%3D~%22.%2B%22%7D%20%7C~%20%22error%22&limit=2&start=$S&end=$E" 2>/dev/null \
  | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin); res=d["data"]["result"]
    print("  ✅ 日志查询返回 %d 条 stream" % len(res))
    for s in res[:2]:
        m=s["stream"]; print("     [%s/%s] %s" % (m.get("namespace"), m.get("pod"), s["values"][0][1][:90]))
except Exception as e:
    print("  ❌", e)
'
echo ""
echo "=== 看板在 Grafana 中的状态 ==="
G=$(kubectl -n monitoring get pods -l app.kubernetes.io/name=grafana -o jsonpath='{.items[0].metadata.name}')
kubectl -n monitoring exec $G -c grafana -- sh -c 'wget -qO- "http://admin:prom-operator@localhost:3000/api/dashboards/uid/wxq-loki-overview"' 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)
    print("  标题:", d["dashboard"]["title"])
    print("  面板数:", len(d["dashboard"]["panels"]))
    print("  变量:", [v["name"] for v in d["dashboard"].get("templating",{}).get("list",[])])
    print("  URL: /d/wxq-loki-overview")
except Exception as e: print("  读取失败:", e)
'
