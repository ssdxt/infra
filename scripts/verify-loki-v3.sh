#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== 1. 变量下拉框能否取到值（Grafana 用的就是这个接口）====="
echo -n "  namespace 取值数: "
kubectl -n logging exec loki-0 -c loki -- wget -qO- 'http://localhost:3100/loki/api/v1/label/namespace/values' 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin)["data"]; print(len(d), d)'
echo -n "  pod 取值数(限定 kube-system): "
kubectl -n logging exec loki-0 -c loki -- wget -qO- 'http://localhost:3100/loki/api/v1/label/pod/values?match%5B%5D=%7Bnamespace%3D%22kube-system%22%7D' 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin)["data"]; print(len(d), "例:", d[:3])'
echo -n "  container 取值数(全集群): "
kubectl -n logging exec loki-0 -c loki -- wget -qO- 'http://localhost:3100/loki/api/v1/label/container/values?match%5B%5D=%7Bnamespace%3D~%22.%2B%22%7D' 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin)["data"]; print(len(d), "例:", d[:4])'
echo ""
echo "===== 2. 日志级别过滤实测（看板 level 变量的 4 个选项）====="
python3 - <<'PY'
import subprocess, urllib.parse, json, time
def q(expr, step="60s"):
    url = "http://localhost:3100/loki/api/v1/query_range?" + urllib.parse.urlencode(
        {"query": expr, "step": step, "start": int(time.time())-10800, "end": int(time.time())})
    t0 = time.time()
    r = subprocess.run(["kubectl","-n","logging","exec","loki-0","-c","loki","--","wget","-qO-",url],
                       capture_output=True, text=True)
    dt = time.time()-t0
    try:
        d = json.loads(r.stdout); n = sum(len(x["values"]) for x in d["data"]["result"])
        return "%.1f 秒, %d 数据点" % (dt, n)
    except Exception:
        return "失败(%.1f秒) %s" % (dt, r.stdout[:80])
SEL = '{namespace=~".+"}'
for name, lv in [("全部", ""), ("错误", ' |~ "(?i)error|fatal|panic|exception"'),
                 ("警告", ' |~ "(?i)warn"'), ("信息", ' |~ "(?i)info"')]:
    expr = 'sum by (namespace) (count_over_time(%s%s [1m]))' % (SEL, lv)
    print("  级别=%-4s %s" % (name, q(expr)))
PY
echo ""
echo "===== 3. 性能对比：旧的 $__auto（约15s步长）vs 新的 1m 步长，3 小时窗口 ====="
python3 - <<'PY'
import subprocess, urllib.parse, json, time
EXPR = 'sum by (namespace) (count_over_time({namespace=~".+"}[%s]))'
def run(step, rng):
    url = "http://localhost:3100/loki/api/v1/query_range?" + urllib.parse.urlencode(
        {"query": EXPR % step, "step": step, "start": int(time.time())-rng, "end": int(time.time())})
    t0=time.time()
    r = subprocess.run(["kubectl","-n","logging","exec","loki-0","-c","loki","--","wget","-qO-",url],
                       capture_output=True,text=True)
    dt=time.time()-t0
    try:
        d=json.loads(r.stdout); pts=sum(len(x["values"]) for x in d["data"]["result"])
        return dt, pts
    except Exception: return dt, -1
for step, rng, label in [("15s", 21600, "旧: 15s 步长 / 6 小时"), ("1m", 10800, "新: 1m 步长 / 3 小时")]:
    dt, pts = run(step, rng)
    print("  %-24s 耗时 %.2f 秒，返回数据点 %d" % (label, dt, pts))
PY
echo ""
echo "===== 4. plant01 的 VictoriaMetrics 现状（判断能否承接日志）====="
curl -s --max-time 8 'http://10.100.10.29:8428/api/v1/status/tsdb' 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)
    for k in ("totalSeries","totalLabelValuePairs","seriesCountByMetricName"):
        v=d.get("data",{}).get(k)
        if isinstance(v,list): print("  %s: top=%s" % (k, v[:3]))
        elif v is not None: print("  %s: %s" % (k, v))
except Exception as e: print("  查询失败:", e)
'
echo -n "  VictoriaMetrics 版本: "
curl -s --max-time 8 'http://10.100.10.29:8428/api/v1/status/buildinfo' 2>/dev/null | head -c 150; echo
echo -n "  是否支持日志接口(/insert/loki 等): "
for p in /insert/loki/api/v1/push /loki/api/v1/push /select/logsql/query; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://10.100.10.29:8428$p" 2>/dev/null)
  echo -n "$p=$code "
done
echo ""
