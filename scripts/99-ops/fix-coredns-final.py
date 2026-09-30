#!/usr/bin/env python3
import json, subprocess, datetime, time

def kcmd(*args):
    return subprocess.run(["kubectl", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")

print("===== 1. CoreDNS：外部域名 NXDOMAIN 秒回 =====")
raw = kcmd("get", "cm", "coredns", "-n", "kube-system", "-o", "json").stdout
d = json.loads(raw)
corefile = d["data"]["Corefile"]
ts = datetime.datetime.now().strftime("%m%d-%H%M")
open(f"/tmp/coredns-bak-{ts}.yaml", "w").write(
    kcmd("get", "cm", "coredns", "-n", "kube-system", "-o", "yaml").stdout)
if "template IN ANY" in corefile:
    print("  已是 NXDOMAIN 模式")
else:
    new = corefile.replace(
        "        forward . /etc/resolv.conf",
        "        template IN ANY . {\n"
        "          rcode NXDOMAIN\n"
        "        }")
    if new == corefile:
        print("  ⚠️ 未匹配，前 25 行原文：")
        print("\n".join(corefile.split("\n")[:25]))
    else:
        d["data"]["Corefile"] = new
        json.dump(d, open("/tmp/coredns-new.json", "w"), ensure_ascii=False)
        r = kcmd("apply", "-f", "/tmp/coredns-new.json")
        print(" ", (r.stdout or r.stderr).strip())
        kcmd("rollout", "restart", "deploy/coredns", "-n", "kube-system")
        subprocess.run(["kubectl","-n","kube-system","rollout","status",
                        "deploy/coredns","--timeout=180s"], capture_output=True, text=True)
        print("  coredns 已重启")

print("")
print("===== 2. WxqLogErrorBurst 规则排除 tetragon（审计事件流是合法日志）=====")
raw = kcmd("get", "cm", "loki-ruler-rules", "-n", "logging", "-o", "json").stdout
d = json.loads(raw)
rules = d["data"]["wxq-log-rules.yaml"]
new = rules.replace('{namespace=~".+"}', '{namespace=~".+",namespace!="tetragon"}')
if new != rules:
    d["data"]["wxq-log-rules.yaml"] = new
    json.dump(d, open("/tmp/ruler-new.json", "w"), ensure_ascii=False)
    kcmd("apply", "-f", "/tmp/ruler-new.json")
    print("  ✅ 规则已排除 tetragon 命名空间")
    # 同步本地源文件
    open("/data1/ssdxt/logging/loki-ruler-rules.yaml", "w").write(new)
else:
    print("  无需修改")
print("")

print("===== 3. 等 90 秒验证 =====")
time.sleep(90)
NOW = int(datetime.datetime.now().timestamp()*1e9)

print("--- 3.1 集群内部 DNS 正常？（起测试 Pod 解析 service）")
r = kcmd("run", "dnstest", "-n", "default", "--rm", "-i", "--restart=Never",
         "--image=harbor.wuxing.local/library/nginx:1.27-alpine", "--command", "--",
         "nslookup", "kubernetes.default.svc.cluster.local")
print("  " + "\n  ".join((r.stdout or "").strip().split("\n")[-4:]))
r2 = kcmd("delete", "pod", "dnstest", "-n", "default", "--force", "--grace-period=0")

print("--- 3.2 kube-system 错误（最近 2 分钟）")
d = loki = None
import urllib.parse
url = "http://localhost:3100/loki/api/v1/query?" + urllib.parse.urlencode(
    {"query": 'sum by (pod) (count_over_time({namespace="kube-system"} |~ "(?i)error" [2m]))'})
r = subprocess.run(["kubectl","-n","logging","exec","loki-0","-c","loki","--","wget","-qO-",url],
                   capture_output=True, text=True)
try:
    dd = json.loads(r.stdout)["data"]["result"]
    if not dd: print("  ✅ = 0")
    for x in dd[:5]: print("  %-40s %6.0f" % (x["metric"].get("pod"), float(x["value"][1])))
except Exception as e: print("  失败", e)

print("--- 3.3 tetragon 事件流（应不再计入告警）")
url = "http://localhost:3100/loki/api/v1/query?" + urllib.parse.urlencode(
    {"query": 'sum(count_over_time({namespace="tetragon"} |~ "(?i)error" [2m]))'})
r = subprocess.run(["kubectl","-n","logging","exec","loki-0","-c","loki","--","wget","-qO-",url],
                   capture_output=True, text=True)
try:
    print("  tetragon 原始错误行仍在日志里（正常，这些是审计事件）:", r.stdout[:80])
except Exception: pass

print("--- 3.4 当前告警")
r = subprocess.run(["kubectl","-n","monitoring","exec",
                    "alertmanager-prometheus-stack-kube-prom-alertmanager-0","-c","alertmanager","--",
                    "wget","-qO-","http://localhost:9093/api/v2/alerts?active=true&silenced=false"],
                   capture_output=True, text=True)
try:
    import collections
    d = json.loads(r.stdout)
    c = collections.Counter((a["labels"].get("severity"), a["labels"].get("alertname")) for a in d)
    for (s, n), k in sorted(c.items()): print("  [%s] %s x%d" % (s, n, k))
    if not c: print("  （无告警）")
except Exception: print("  解析失败")