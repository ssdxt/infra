#!/usr/bin/env python3
import json, subprocess, urllib.parse, datetime

def loki(path, params=None):
    url = "http://localhost:3100" + path + ("?" + urllib.parse.urlencode(params) if params else "")
    r = subprocess.run(["kubectl","-n","logging","exec","loki-0","-c","loki","--","wget","-qO-",url],
                       capture_output=True, text=True)
    try: return json.loads(r.stdout)
    except Exception: return {"err": r.stdout[:100], "stderr": r.stderr[:100]}

now = int(datetime.datetime.now().timestamp()*1e9)
hour = int(datetime.datetime.now().timestamp()*1e9) - 3600*int(1e9)//int(1e9)  # noqa

print("===== 1. kube-apiserver 错误趋势（5分钟一档，近1小时）=====")
d = loki("/loki/api/v1/query_range", {
    "query": 'sum(count_over_time({namespace="kube-system",pod=~"kube-apiserver.*"} |~ "(?i)error" [5m]))',
    "start": int(datetime.datetime.now().timestamp()*1e9) - 3600*10**9,
    "end":   int(datetime.datetime.now().timestamp()*1e9), "step": 300*10**9})
try:
    for ts, v in d["data"]["result"][0]["values"][-12:]:
        t = datetime.datetime.fromtimestamp(float(ts)).strftime("%H:%M")
        print("  %s  %6d  %s" % (t, float(v), "█"*min(int(float(v)/100)+1, 40)))
except Exception as e: print("  失败:", str(d)[:200])

print("")
print("===== 2. apiserver 错误分类（最近5分钟样本）=====")
d = loki("/loki/api/v1/query_range", {
    "query": '{namespace="kube-system",pod=~"kube-apiserver.*"} |~ "(?i)error"',
    "start": int(datetime.datetime.now().timestamp()*1e9) - 300*10**9,
    "end":   int(datetime.datetime.now().timestamp()*1e9), "limit": 200})
try:
    import collections, re
    cnt = collections.Counter(); sample = {}
    for s in d["data"]["result"]:
        for ts, line in s["values"]:
            m = re.search(r'err="([^"]{0,90})', line)
            key = m.group(1)[:70] if m else line[:70]
            key = re.sub(r"[\d.]{7,}", "IP", key); key = re.sub(r"0x[0-9a-f]+", "X", key)
            cnt[key] += 1
            sample.setdefault(key, line[:140])
    for k, n in cnt.most_common(8):
        print("  %4d 条  %s" % (n, k))
        if n >= cnt.most_common(1)[0][1]: print("        例:", sample[k][:130])
except Exception as e: print("  失败:", e, str(d)[:150])

print("")
print("===== 3. nodelocaldns 错误内容（近5分钟）=====")
d = loki("/loki/api/v1/query_range", {
    "query": '{namespace="kube-system",pod=~"nodelocaldns.*"} |~ "(?i)error"',
    "start": int(datetime.datetime.now().timestamp()*1e9) - 300*10**9,
    "end":   int(datetime.datetime.now().timestamp()*1e9), "limit": 50})
try:
    import collections
    cnt = collections.Counter(); sample = {}
    for s in d["data"]["result"]:
        for ts, line in s["values"]:
            m = re.search(r'\[ERROR\] (.*)', line)
            key = (m.group(1)[:80] if m else line[:80])
            key = re.sub(r"a\d+\.", "aX.", key)
            cnt[key] += 1; sample.setdefault(key, line[:150])
    for k, n in cnt.most_common(5):
        print("  %4d 条  %s" % (n, k))
        if n == cnt.most_common(1)[0][1]: print("        例:", sample[k][:140])
except Exception as e: print("  失败:", e, str(d)[:150])