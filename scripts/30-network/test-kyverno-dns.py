#!/usr/bin/env python3
import json, subprocess, datetime, time

def kcmd(*args):
    return subprocess.run(["kubectl", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")

print("===== 1. Kyverno 现状 =====")
print(kcmd("get", "pods", "-n", "kyverno", "--no-headers").stdout.strip() or "  无 Pod")
print("  --- webhook 配置与 failurePolicy")
for kind in ["mutatingwebhookconfigurations", "validatingwebhookconfigurations"]:
    r = kcmd("get", kind, "-o", "json")
    try:
        d = json.loads(r.stdout)
        for w in d["items"]:
            for wh in w.get("webhooks", []):
                print("  %s: %s failurePolicy=%s" % (kind, wh.get("name"), wh.get("failurePolicy")))
    except Exception: print("  （解析失败）")
print("")
print("--- 最近 webhook 相关事件")
r = kcmd("get", "events", "-A", "--sort-by=.lastTimestamp")
for ln in (r.stdout or "").split("\n"):
    if "webhook" in ln.lower() and ("fail" in ln.lower() or "error" in ln.lower()):
        print("  " + ln[:160])

print("")
print("===== 2. 决定性实验：缩容 Kyverno → 测 DNS =====")
print(kcmd("scale", "deploy", "--all", "-n", "kyverno", "--replicas=0").stdout.strip())
time.sleep(20)
NOW = int(datetime.datetime.now().timestamp()*1e9)

def dnstest(server, name):
    r = kcmd("run", f"dt-{server.replace('.','')}-{int(time.time())}", "-n", "default",
             "--rm", "-i", "--restart=Never", "--image=harbor.wuxing.local/library/nginx:1.27-alpine",
             "--command", "--", "sh", "-c",
             f"nslookup {name} {server} 2>&1 | tail -3")
    return (r.stdout or "").strip()

print("  --- 缩容 Kyverno 后：cluster.local 解析测试")
print("  " + dnstest("169.254.25.10", "kubernetes.default.svc.cluster.local").replace("\n", "\n  "))
print("  --- 缩容 Kyverno 后：外部域名测试")
print("  " + dnstest("169.254.25.10", "www.baidu.com").replace("\n", "\n  "))
print("")
print("===== 3. 结论判定 =====")
r = kcmd("run", "dtfinal", "-n", "default", "--rm", "-i", "--restart=Never",
         "--image=harbor.wuxing.local/library/nginx:1.27-alpine", "--command", "--",
         "sh", "-c", "getent hosts kubernetes.default.svc.cluster.local && echo CLUSTER_DNS_OK")
ok = "CLUSTER_DNS_OK" in (r.stdout or "")
print("  集群内部 DNS:", "✅ 恢复（Kyverno 是原因）" if ok else "❌ 仍异常（Kyverno 缩容也没救回，另有原因）")
print("")
print("===== 4. 当前告警 =====")
r = kcmd("exec", "-n", "monitoring", "alertmanager-prometheus-stack-kube-prom-alertmanager-0",
         "-c", "alertmanager", "--", "wget", "-qO-",
         "http://localhost:9093/api/v2/alerts?active=true&silenced=false")
import collections
try:
    d2 = json.loads(r.stdout)
    c = collections.Counter((a["labels"].get("severity"), a["labels"].get("alertname")) for a in d2)
    for (s, n), k in sorted(c.items()): print("  [%s] %s x%d" % (s, n, k))
    if not c: print("  （无告警 🎉）")
except Exception: print("  解析失败")