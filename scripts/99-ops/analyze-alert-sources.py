#!/usr/bin/env python3
import json, subprocess, urllib.parse, datetime, re, collections

def loki(path, params=None):
    url = "http://localhost:3100" + path + ("?" + urllib.parse.urlencode(params) if params else "")
    r = subprocess.run(["kubectl","-n","logging","exec","loki-0","-c","loki","--","wget","-qO-",url],
                       capture_output=True, text=True)
    try: return json.loads(r.stdout)
    except Exception: return {"data":{"result":[]}}

NOW = int(datetime.datetime.now().timestamp()*1e9)

print("===== 1. tetragon 命名空间：608 条/5m 的错误是什么 =====")
d = loki("/loki/api/v1/query_range", {
    "query": '{namespace="tetragon"} |~ "(?i)error"',
    "start": NOW - 600*10**9, "end": NOW, "limit": 100})
try:
    cnt = collections.Counter(); sample = {}
    for s in d["data"]["result"]:
        pod = s["metric"].get("pod","?")
        for ts, line in s["values"]:
            m = re.search(r'(msg="[^"]{0,80}|error[^"]{0,80}|level=\w+)', line)
            key = re.sub(r"[\d.]{5,}", "N", (m.group(1) if m else line[:70]))
            cnt[(pod, key)] += 1
            sample.setdefault((pod, key), line[:160])
    for (pod, key), n in cnt.most_common(6):
        print("  %4d 条  [%s] %s" % (n, pod, key))
        print("          例:", sample[(pod,key)][:140])
except Exception as e: print("  失败:", e, str(d)[:150])

print("")
print("===== 2. kube-system：6118 条/5m 的构成分解 =====")
d = loki("/loki/api/v1/query", {"query": 'sum by (pod) (count_over_time({namespace="kube-system"} |~ "(?i)error" [5m]))'})
try:
    for r in sorted(d["data"]["result"], key=lambda x: -float(x["value"][1]))[:6]:
        print("  %-42s %6.0f 条" % (r["metric"].get("pod"), float(r["value"][1])))
except Exception as e: print("  失败", e)

print("")
print("===== 3. coredns 错误分类（还是 . NS 超时吗）=====")
d = loki("/loki/api/v1/query_range", {
    "query": '{namespace="kube-system",pod=~"coredns.*"} |~ "(?i)error"',
    "start": NOW - 300*10**9, "end": NOW, "limit": 200})
try:
    cnt = collections.Counter()
    for s in d["data"]["result"]:
        for ts, line in s["values"]:
            m = re.search(r'errors: \d+ ([^:]{0,40}):', line)
            key = m.group(1) if m else ("." if ". NS:" in line else line[:50])
            cnt[re.sub(r"[\d.]{5,}", "N", key)] += 1
    for k, n in cnt.most_common(6): print("  %5d 条  %s" % (n, k))
except Exception as e: print("  失败:", e)

print("")
print("===== 4. nodelocaldns 错误分类（近5分钟）=====")
d = loki("/loki/api/v1/query_range", {
    "query": '{namespace="kube-system",pod=~"nodelocaldns.*"} |~ "(?i)error"',
    "start": NOW - 300*10**9, "end": NOW, "limit": 100})
try:
    cnt = collections.Counter()
    for s in d["data"]["result"]:
        for ts, line in s["values"]:
            m = re.search(r'(stats\.[a-z.]+|\d+ [^:]{0,30}:)', line)
            key = m.group(1) if m else line[:50]
            cnt[re.sub(r"[\d.]{5,}", "N", key)] += 1
    for k, n in cnt.most_common(5): print("  %5d 条  %s" % (n, k))
except Exception as e: print("  失败:", e)

print("")
print("===== 5. 趋势：CoreDNS 错误是上升还是稳定 =====")
d = loki("/loki/api/v1/query_range", {
    "query": 'sum(count_over_time({namespace="kube-system",pod=~"coredns.*"} |~ "(?i)error" [10m]))',
    "start": NOW - 7200*10**9, "end": NOW, "step": 600*10**9})
try:
    for ts, v in d["data"]["result"][0]["values"][-12:]:
        t = datetime.datetime.fromtimestamp(float(ts)).strftime("%H:%M")
        print("  %s  %6.0f 条/10min" % (t, float(v)))
except Exception as e: print("  失败", e)