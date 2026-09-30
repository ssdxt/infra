#!/usr/bin/env python3
import json, subprocess, time

def kcmd(*args):
    return subprocess.run(["kubectl", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")

# 已知的原始（forward 模式）Corefile —— 来自最早打印的原文
ORIGINAL_COREFILE = """.:53 {
  cache 30
  errors
  ready
  prometheus :9153
  loop
  reload
  loadbalance

  health {
    lameduck 5s
  }
  kubernetes cluster.local in-addr.arpa ip6.arpa {
    pods insecure
    fallthrough in-addr.arpa ip6.arpa
    ttl 30
  }
  forward . /etc/resolv.conf {
    max_concurrent 1000
  }
}
"""

print("===== P0：恢复 coredns Corefile（forward 模式）=====")
cur = json.loads(kcmd("get", "cm", "coredns", "-n", "kube-system", "-o", "json").stdout)
cur["data"]["Corefile"] = ORIGINAL_COREFILE
json.dump(cur, open("/tmp/coredns-restore.json", "w"), ensure_ascii=False)
r = kcmd("apply", "--force-conflicts", "-f", "/tmp/coredns-restore.json")
print("  apply:", (r.stdout or r.stderr).strip())
kcmd("rollout", "restart", "deploy", "coredns", "-n", "kube-system")
subprocess.run(["kubectl","-n","kube-system","rollout","status","deploy/coredns","--timeout=180s"],
               capture_output=True, text=True)
print("  rollout 完成")

print("")
print("===== 验证 1：集群内部 DNS =====")
time.sleep(20)
r = kcmd("run", "dv3", "-n", "default", "--rm", "-i", "--restart=Never",
         "--image=harbor.wuxing.local/library/nginx:1.27-alpine", "--command", "--",
         "sh", "-c",
         "getent hosts kubernetes.default.svc.cluster.local && echo CLUSTER_OK; "
         "getent hosts prometheus-stack-grafana.monitoring.svc.cluster.local && echo GRAFANA_OK; "
         "nslookup www.baidu.com 169.254.25.10 2>&1 | tail -2")
print((r.stdout or "").strip()[:500])
r = kcmd("delete", "pod", "dv3", "-n", "default", "--force", "--grace-period=0")

print("")
print("===== 验证 2：关键服务连通 =====")
for tgt in ["http://loki-0.logging.svc.cluster.local:3100/ready",
            "http://prometheus-stack-grafana.monitoring.svc.cluster.local/api/health"]:
    r = kcmd("exec", "-n", "logging", "loki-0", "-c", "loki", "--",
             "wget", "-q", "-O-", "-T", "5", tgt)
    code = "OK" if r.stdout else "FAIL"
    print(f"  {tgt}: {code}")

print("")
print("===== 验证 3：最终告警 =====")
time.sleep(20)
r = kcmd("exec", "-n", "monitoring", "alertmanager-prometheus-stack-kube-prom-alertmanager-0",
         "-c", "alertmanager", "--", "wget", "-qO-",
         "http://localhost:9093/api/v2/alerts?active=true&silenced=false")
import collections, json
try:
    d = json.loads(r.stdout)
    c = collections.Counter((a["labels"].get("severity"), a["labels"].get("alertname")) for a in d)
    for (s, n), k in sorted(c.items()): print("  [%s] %s x%d" % (s, n, k))
    if not c: print("  （无告警 🎉）")
except Exception: print("  解析失败")