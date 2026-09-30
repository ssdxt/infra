#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== 1. Loki 服务状态 ====="
kubectl -n logging get pods --no-headers 2>/dev/null | awk '{print "  "$1, $2, $3}'
kubectl -n logging get svc loki --no-headers 2>/dev/null | awk '{print "  svc: "$1, $2, $3, $5}'
echo ""
echo "===== 2. Grafana 里是否已配好 Loki 数据源 ====="
kubectl -n monitoring get cm --no-headers 2>/dev/null | grep -i loki | sed 's/^/  /' || echo "  没找到 loki 数据源 ConfigMap"
POD=$(kubectl -n monitoring get pods -l app.kubernetes.io/name=grafana --no-headers 2>/dev/null | head -1 | awk '{print $1}')
echo "  Grafana Pod: $POD"
kubectl -n monitoring exec $POD -c grafana -- sh -c 'wget -qO- --header="Content-Type: application/json" "http://admin:<GRAFANA_PASSWORD>@localhost:3000/api/datasources" 2>/dev/null' 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)
    for x in d: print("   -", x.get("name"), "|", x.get("type"), "|", x.get("url"), "| default=", x.get("isDefault"))
except Exception as e: print("   查询失败:", e)
'
echo ""
echo "===== 3. 当前有哪些标签（= 能按什么筛选）====="
kubectl -n logging exec loki-0 -c loki -- wget -qO- 'http://localhost:3100/loki/api/v1/labels' 2>/dev/null | head -c 400; echo
echo ""
echo "===== 4. 各命名空间日志量（5 分钟）====="
kubectl -n logging exec loki-0 -c loki -- wget -qO- 'http://localhost:3100/loki/api/v1/query?query=sum(count_over_time(%7Bnamespace%3D~%22.%2B%22%7D%5B5m%5D))%20by%20(namespace)' 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)
    for r in d["data"]["result"]:
        print("   %-22s %s 行" % (r["metric"].get("namespace"), r["value"][1]))
except Exception as e: print("   查询失败")
'
echo ""
echo "===== 5. 实测一条真实日志（monitoring 命名空间）====="
kubectl -n logging exec loki-0 -c loki -- wget -qO- 'http://localhost:3100/loki/api/v1/query?query=%7Bnamespace%3D%22monitoring%22%7D&limit=2' 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)
    for s in d["data"]["result"][:2]:
        m=s["stream"]
        print("   [%s/%s/%s] node=%s" % (m.get("namespace"), m.get("pod"), m.get("container"), m.get("node")))
        for v in s["values"][:1]:
            print("     ", v[1][:150])
except Exception as e: print("   查询失败:", e)
'
echo ""
echo "===== 6. 实测：找错误日志（全集群 grep error）====="
kubectl -n logging exec loki-0 -c loki -- wget -qO- 'http://localhost:3100/loki/api/v1/query?query=%7Bnamespace%3D~%22.%2B%22%7D%20%7C%3D%20%22error%22&limit=3' 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)
    n=0
    for s in d["data"]["result"][:3]:
        m=s["stream"]; n+=1
        print("   [%s/%s]" % (m.get("namespace"), m.get("pod")))
        for v in s["values"][:1]: print("     ", v[1][:120])
    if n==0: print("    （该时间窗没有匹配）")
except Exception as e: print("   查询失败")
'
echo ""
echo "===== 7. 入口地址（浏览器访问 Grafana）====="
echo "  http://10.100.10.10:32298          （NodePort，你本机可直接开）"
echo "  或 http://grafana.wuxing.local:32298 （需先解决本机 DNS 劫持/路由）"
echo "  登录: admin / <GRAFANA_PASSWORD>    → 左侧 Explore → 数据源选 Loki"
