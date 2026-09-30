#!/usr/bin/env python3
import json, subprocess, datetime, time

def kcmd(*args):
    return subprocess.run(["kubectl", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")

print("===== 1. 按真实缩进替换 forward → template NXDOMAIN =====")
raw = kcmd("get", "cm", "coredns", "-n", "kube-system", "-o", "json").stdout
d = json.loads(raw)
corefile = d["data"]["Corefile"]
OLD = """  forward . /etc/resolv.conf {
    max_concurrent 1000
  }"""
NEW = """  template IN ANY . {
    rcode NXDOMAIN
  }"""
if OLD in corefile:
    d["data"]["Corefile"] = corefile.replace(OLD, NEW)
    json.dump(d, open("/tmp/coredns-new.json", "w"), ensure_ascii=False)
    r = kcmd("apply", "-f", "/tmp/coredns-new.json")
    print(" ", (r.stdout or r.stderr).strip())
    kcmd("rollout", "restart", "deploy/coredns", "-n", "kube-system")
    subprocess.run(["kubectl","-n","kube-system","rollout","status",
                    "deploy/coredns","--timeout=180s"], capture_output=True, text=True)
    print("  coredns 已重启")
else:
    print("  ⚠️ 仍未匹配（检查缩进）")

print("")
print("===== 2. 验证 =====")
time.sleep(30)
# 集群内 DNS
r = kcmd("run", "dnstest2", "-n", "default", "--rm", "-i", "--restart=Never",
         "--image=harbor.wuxing.local/library/nginx:1.27-alpine", "--command", "--",
         "sh", "-c", "nslookup kubernetes.default.svc.cluster.local 2>&1 | head -4; echo ---; nslookup www.baidu.com 2>&1 | head -3")
print((r.stdout or "").strip()[:400])
r = kcmd("delete", "pod", "dnstest2", "-n", "default", "--force", "--grace-period=0")

print("")
print("===== 3. 等 90 秒验证错误消失 =====")
time.sleep(90)
NOW = int(datetime.datetime.now().timestamp()*1e9)
import urllib.parse
url = "http://localhost:3100/loki/api/v1/query?" + urllib.parse.urlencode(
    {"query": 'sum by (pod) (count_over_time({namespace="kube-system"} |~ "(?i)error" [2m]))'})
r = subprocess.run(["kubectl","-n","logging","exec","loki-0","-c","loki","--","wget","-qO-",url],
                   capture_output=True, text=True)
try:
    dd = json.loads(r.stdout)["data"]["result"]
    if not dd: print("  ✅ kube-system 错误 = 0")
    for x in dd[:5]: print("  %-42s %6.0f 条/2min" % (x["metric"].get("pod"), float(x["value"][1])))
except Exception as e: print("  失败", e)
print("")
print("--- 当前告警 ---")
r = kcmd("exec", "-n", "monitoring",
         "alertmanager-prometheus-stack-kube-prom-alertmanager-0", "-c", "alertmanager", "--",
         "wget", "-qO-", "http://localhost:9093/api/v2/alerts?active=true&silenced=false")
import collections
try:
    d2 = json.loads(r.stdout)
    c = collections.Counter((a["labels"].get("severity"), a["labels"].get("alertname")) for a in d2)
    for (s, n), k in sorted(c.items()): print("  [%s] %s x%d" % (s, n, k))
    if not c: print("  （无告警 🎉）")
except Exception: print(r.stdout[:200])