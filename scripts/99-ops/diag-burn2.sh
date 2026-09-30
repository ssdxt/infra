#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
PP="prometheus-prometheus-stack-kube-prom-prometheus-0"
q() { kubectl -n monitoring exec $PP -c prometheus -- wget -qO- "http://localhost:9090/api/v1/query?query=$1" 2>/dev/null; }

echo "===== 1. KubeAPIErrorBudgetBurn 触发详情（哪个窗口在烧）====="
q "ALERTS%7Balertname%3D%22KubeAPIErrorBudgetBurn%22%2Calertstate%3D%22firing%22%7D" 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)["data"]["result"]
    if not d: print("  ✅ 已无 firing 的燃烧告警")
    for r in d:
        m=r["metric"]
        print("  [%s] long=%s short=%s since=%s" % (m.get("severity"), m.get("long"), m.get("short"), r["activeAt"][:19]))
except Exception as e: print("  失败", e)
'
echo ""
echo "===== 2. apiserver 最近5分钟全部状态码分布 ====="
q "sum%20by%20(code)%20(rate(apiserver_request_total%5B5m%5D))" 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)["data"]["result"]
    rows=sorted(((r["metric"].get("code","?"),float(r["value"][1])) for r in d), key=lambda x:-x[1])[:10]
    total=sum(x[1] for x in rows)
    for c,rate in rows: print("  code=%-4s %8.2f/s  (%.1f%%)" % (c, rate, rate/total*100 if total else 0))
    print("  合计 %.1f/s" % total)
except Exception as e: print("  失败", e)
'
echo ""
echo "===== 3. 5xx 具体是哪些（verb/resource/code 拆开）====="
q "topk(10%2C%20sum%20by%20(code%2Cverb%2Cresource)%20(rate(apiserver_request_total%7Bcode%3D~%225..%7D%5B30m%5D)))" 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)["data"]["result"]
    if not d: print("  ✅ 近30分钟无 5xx")
    for r in d: print("  code=%s %-8s %-22s %.3f/s" % (r["metric"].get("code"), r["metric"].get("verb"), r["metric"].get("resource") or "-", float(r["value"][1])))
except Exception as e: print("  失败", e)
'
echo ""
echo "===== 4. etcd 指标是否已被监控（另一子智能体在打通）====="
q "count(up%7Bjob%3D~%22.*etcd.*%22%7D)" 2>/dev/null | head -c 150; echo
q "histogram_quantile(0.99%2C%20sum%20by%20(le)%20(rate(etcd_disk_wal_fsync_duration_seconds_bucket%5B5m%5D)))" 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)["data"]["result"]
    if not d: print("  etcd fsync p99: 无数据（监控还没打通）")
    else:
        for r in d: print("  ✅ etcd WAL fsync p99 = %.1f ms" % (float(r["value"][1])*1000))
except Exception: print("  查询失败")
'
echo ""
echo "===== 5. hubble-relay OOM 详情 ====="
kubectl -n kube-system get deploy hubble-relay -o wide 2>/dev/null | sed 's/^/  /' || echo "  无此 deployment"
kubectl -n kube-system get deploy hubble-relay -o jsonpath='{.spec.template.spec.containers[0].resources}' 2>/dev/null; echo ""
kubectl -n kube-system get pods | grep hubble-relay | sed 's/^/  /'
echo -n "  OOM 前日志尾部: "
kubectl -n kube-system logs deploy/hubble-relay --previous --tail=5 2>/dev/null | tail -3 | head -c 300; echo ""