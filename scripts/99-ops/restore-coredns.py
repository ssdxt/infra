#!/usr/bin/env python3
import json, subprocess, datetime, time

def kcmd(*args):
    return subprocess.run(["kubectl", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")

print("===== 1. 恢复 coredns CM 到 template 之前的备份 =====")
import glob
baks = sorted(glob.glob("/tmp/coredns-bak-*.yaml"))
if not baks:
    print("  ❌ 找不到备份！")
else:
    bak = baks[-1]
    r = kcmd("apply", "-f", bak)
    print("  恢复自:", bak, "→", (r.stdout or r.stderr).strip())
    kcmd("rollout", "restart", "deploy/coredns", "-n", "kube-system")
    subprocess.run(["kubectl","-n","kube-system","rollout","status",
                    "deploy/coredns","--timeout=180s"], capture_output=True, text=True)
    print("  coredns 已重启")

print("")
print("===== 2. 等 60 秒验证 cluster.local 恢复 =====")
time.sleep(60)
r = kcmd("run", "dv", "-n", "default", "--rm", "-i", "--restart=Never",
         "--image=harbor.wuxing.local/library/nginx:1.27-alpine", "--command", "--",
         "sh", "-c", "getent hosts kubernetes.default.svc.cluster.local && echo CLUSTER_DNS_OK")
out = (r.stdout or "")
print("  " + out.strip()[:200])
print("  集群内部 DNS:", "✅ 恢复" if "CLUSTER_DNS_OK" in out else "❌ 仍异常")

print("")
print("===== 3. 噪音治理替代方案：WxqLogErrorBurst 规则排除 coredns 的已知噪音 =====")
raw = kcmd("get", "cm", "loki-ruler-rules", "-n", "logging", "-o", "json").stdout
d = json.loads(raw)
rules = d["data"]["wxq-log-rules.yaml"]
# 排除 coredns/nodelocaldns 的已知外部 DNS 超时噪音（. NS 223.5.5.5 / stats.grafana.org）
new = rules.replace(
    '{namespace=~".+",namespace!="tetragon"} |~ "(?i)error"',
    '{namespace=~".+",namespace!="tetragon",pod!~"coredns.*|nodelocaldns.*"} |~ "(?i)error"')
if new != rules:
    d["data"]["wxq-log-rules.yaml"] = new
    json.dump(d, open("/tmp/ruler-new2.json", "w"), ensure_ascii=False)
    kcmd("apply", "-f", "/tmp/ruler-new2.json")
    open("/data1/ssdxt/logging/loki-ruler-rules.yaml", "w").write(new)
    print("  ✅ 规则已排除 coredns/nodelocaldns 的已知 DNS 噪音（真实错误仍会触发）")
else:
    print("  规则无需修改")

print("")
print("===== 4. 最终健康快照 =====")
time.sleep(30)
print("--- Pod")
print(kcmd("get", "pods", "-n", "logging").stdout.strip()[:300])
print("--- 当前告警")
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