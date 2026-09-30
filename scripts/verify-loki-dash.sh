#!/bin/bash
# 验证看板里每条 LogQL 都能出数据
q() {
  local desc="$1" expr="$2"
  echo -n "  [$desc] "
  kubectl -n logging exec loki-0 -c loki -- sh -c "wget -qO- --post-data='query='$expr 'http://localhost:3100/loki/api/v1/query'" 2>/dev/null | head -c 200
  echo ""
}
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== 逐个面板的查询实测 ====="
echo "  1) 各命名空间日志量:"
python3 - <<'PY'
import subprocess, urllib.parse, json
def q(expr):
    url = "http://localhost:3100/loki/api/v1/query?" + urllib.parse.urlencode({"query": expr})
    r = subprocess.run(["kubectl","-n","logging","exec","loki-0","-c","loki","--","wget","-qO-",url],
                       capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
        res = d.get("data",{}).get("result",[])
        return "OK  %d 条序列" % len(res) if res else "空结果(可能语法OK但无数据)"
    except Exception:
        return "❌ 失败: " + (r.stdout[:100] or r.stderr[:100])

tests = [
 ("面板1 各命名空间日志量",   'sum by (namespace) (count_over_time({namespace=~".+"}[5m]))'),
 ("面板2 Top10 Pod",          'topk(10, sum by (pod) (count_over_time({namespace=~".+"}[5m])))'),
 ("面板3 错误速率",           'sum by (namespace) (count_over_time({namespace=~".+"} |~ "(?i)error|fail|panic|exception|timeout|refused" [5m]))'),
 ("面板4 错误Top10 Pod",      'topk(10, sum by (pod) (count_over_time({namespace=~".+"} |~ "(?i)error|fail|panic|exception" [5m])))'),
 ("面板5 stdout/stderr",      'sum by (stream) (count_over_time({namespace=~".+"}[5m]))'),
 ("面板6 按容器 Top10",       'topk(10, sum by (container) (count_over_time({namespace=~".+"}[5m])))'),
 ("面板7 按节点",             'sum by (node) (count_over_time({namespace=~".+"}[5m]))'),
 ("面板8 实时错误日志",       '{namespace=~".+"} |~ "(?i)error|fail|panic|exception|timeout|refused"'),
 ("面板9 日志浏览器",         '{namespace=~".+"}'),
 ("变量 namespace 取值",      'count by (namespace) (count_over_time({namespace=~".+"}[5m]))'),
]
for desc, expr in tests:
    print("  %-24s %s" % (desc, q(expr)))
PY
echo ""
echo "===== 看板加载状态（Grafana API）====="
G=$(kubectl -n monitoring get pods -l app.kubernetes.io/name=grafana -o jsonpath='{.items[0].metadata.name}')
kubectl -n monitoring exec $G -c grafana -- sh -c 'wget -qO- --header="Content-Type: application/json" "http://admin:prom-operator@localhost:3000/api/search?query=Loki"' 2>/dev/null | python3 -c '
import sys,json
for x in json.load(sys.stdin): print("  ", x.get("title"), "->", x.get("url"))
'
echo ""
echo "===== 侧车是否已加载该 ConfigMap ====="
kubectl -n monitoring logs -l app.kubernetes.io/name=grafana -c grafana-sc-dashboard --tail=8 2>/dev/null | grep -i -E 'loki|dashboard' | tail -5 | sed 's/^/  /'
