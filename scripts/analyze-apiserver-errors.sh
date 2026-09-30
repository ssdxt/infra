#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
loki() { kubectl -n logging exec loki-0 -c loki -- wget -qO- "http://localhost:3100/loki/api/v1/query?query=$1" 2>/dev/null; }

echo "===== 1. kube-apiserver 错误趋势（每5分钟，近1小时）====="
loki 'sum(count_over_time(%7Bnamespace%3D%22kube-system%22%2Cpod%3D~%22kube-apiserver.*%22%7D%20%7C~%20%22(?i)error%22%20%5B5m%5D))' 2>/dev/null | python3 -c '
import sys, json, datetime
try:
    d = json.load(sys.stdin)["data"]["result"]
    for s in d:
        for ts, v in s["values"][-12:]:
            t = datetime.datetime.fromtimestamp(float(ts)).strftime("%H:%M")
            bar = "█" * min(int(float(v)/50)+1, 40)
            print("  %s  %5d  %s" % (t, float(v), bar))
except Exception as e: print("  失败", e)
'
echo ""
echo "===== 2. 最近 5 分钟 apiserver 错误内容采样（分类用）====="
loki '{namespace%3D%22kube-system%22%2Cpod%3D~%22kube-apiserver.*%22%7D%20%7C~%20%22(?i)error%22' 2>/dev/null | python3 -c '
import sys, json, re, collections
try:
    d = json.load(sys.stdin)["data"]["result"]
    pat = collections.Counter()
    samples = {}
    for s in d:
        for ts, line in s["values"]:
            for key in ["custom.metrics", "out of order", "Handler timeout", "context deadline", "http2: stream closed", "TLS handshake", "connection refused", "etcd", "apiservice", "Unauthorized"]:
                if key.lower() in line.lower():
                    pat[key] += 1
                    samples.setdefault(key, line[:160])
                    break
            else:
                pat["其他"] += 1
                samples.setdefault("其他", line[:160])
    for k, n in pat.most_common():
        print("  %-24s %4d 条   例: %s" % (k, n, samples[k][:110]))
except Exception as e: print("  失败", e)
'
echo ""
echo "===== 3. nodelocaldns 错误采样（近1小时）====="
loki 'sum(count_over_time(%7Bnamespace%3D%22kube-system%22%2Cpod%3D~%22nodelocaldns.*%22%7D%20%7C~%20%22(?i)error%22%20%5B1h%5D))%20by%20(pod)' 2>/dev/null | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)["data"]["result"]
    for r in sorted(d, key=lambda x: -float(x["value"][1]))[:6]:
        print("  %-30s %s 条/时" % (r["metric"].get("pod"), r["value"][1]))
except Exception as e: print("  失败", e)
'
echo -n "  错误内容采样: "
loki '{namespace%3D%22kube-system%22%2Cpod%3D~%22nodelocaldns.*%22%7D%20%7C~%20%22(?i)error%22' 2>/dev/null | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)["data"]["result"]
    for s in d[:1]:
        for ts, line in s["values"][:1]: print(line[:180])
except Exception: print("无")
'
echo ""
echo "===== 4. 最近 15 分钟错误总量（判断是否已恢复稳态）====="
for w in "10m" "30m" "1h"; do
  echo -n "  近$w: "
  loki "sum(count_over_time(%7Bnamespace%3D%22kube-system%22%7D%20%7C~%20%22(?i)error%22%20%5B$w%5D))" 2>/dev/null | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)["data"]["result"]
    print("%s 条" % ("%.0f" % float(d["data"]["result"][0]["value"][1]) if d["data"]["result"] else "0"))
except Exception: print("?")
'
done