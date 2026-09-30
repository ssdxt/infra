#!/usr/bin/env python3
import json, subprocess, urllib.parse, datetime, collections

def loki(path, params=None):
    url = "http://localhost:3100" + path + ("?" + urllib.parse.urlencode(params) if params else "")
    r = subprocess.run(["kubectl","-n","logging","exec","loki-0","-c","loki","--","wget","-qO-",url],
                       capture_output=True, text=True)
    try: return json.loads(r.stdout)
    except Exception: return {"data":{"result":[]}}

NOW = int(datetime.datetime.now().timestamp()*1e9)

print("===== 1. kube-system 错误趋势（10分钟一档，近2小时）=====")
d = loki("/loki/api/v1/query_range", {
    "query": 'sum by (pod) (count_over_time({namespace="kube-system",pod=~"kube-apiserver.*|coredns.*|nodelocaldns.*"} |~ "(?i)error" [10m]))',
    "start": NOW - 7200*10**9, "end": NOW, "step": 600*10**9})
try:
    tot = {}
    for s in d["data"]["result"]:
        pod = s["metric"].get("pod","?")
        for ts, v in s["values"][-12:]:
            tot.setdefault(ts, 0); tot[ts] = tot.get(ts,0) + float(v)
    for ts in sorted(tot)[-12:]:
        t = datetime.datetime.fromtimestamp(float(ts)).strftime("%H:%M")
        print("  %s  %6.0f 条/10min  %s" % (t, tot[ts], "█"*min(int(tot[ts]/50)+1, 40)))
except Exception as e: print("  失败:", e, str(d)[:150])

print("")
print("===== 2. 各 Pod 错误量（近30分钟）=====")
d = loki("/loki/api/v1/query", {"query": 'sum by (pod) (count_over_time({namespace="kube-system",pod=~"kube-apiserver.*|coredns.*|nodelocaldns.*"} |~ "(?i)error" [30m]))'})
try:
    for r in sorted(d["data"]["result"], key=lambda x: -float(x["value"][1]))[:8]:
        print("  %-40s %6.0f 条" % (r["metric"].get("pod"), float(r["value"][1])))
except Exception as e: print("  失败", e)

print("")
print("===== 3. 错误内容分类（近15分钟，去重采样）====="
      )
d = loki("/loki/api/v1/query_range", {
    "query": '{namespace="kube-system",pod=~"kube-apiserver.*|coredns.*|nodelocaldns.*"} |~ "(?i)error"',
    "start": NOW - 900*10**9, "end": NOW, "limit": 300})
import re
try:
    cnt = collections.Counter(); sample = {}
    for s in d["data"]["result"]:
        for ts, line in s["values"]:
            m = re.search(r'(err="[^"]{0,80}|\[ERROR\][^"]{0,80}|level=error[^"]{0,60})', line)
            key = re.sub(r"[\d.]{7,}", "IP", (m.group(1) if m else line[:70]))
            cnt[key] += 1; sample.setdefault(key, line[:150])
    if not cnt: print("  ✅ 近15分钟无错误日志")
    for k, n in cnt.most_common(8):
        print("  %5d 条  %s" % (n, k))
        if n == cnt.most_common(1)[0][1]: print("        例:", sample[k][:130])
except Exception as e: print("  失败:", e, str(d)[:120])