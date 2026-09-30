#!/usr/bin/env python3
import json, subprocess, time

def kcmd(*args):
    return subprocess.run(["kubectl", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")

print("===== P0 修复：用当前 CM 为基底、只替换 Corefile 数据，强制覆盖 =====")
import glob
# 找最初的备份（forward 模式）
bak_files = sorted(glob.glob("/tmp/coredns-bak-*.yaml"))
backup_corefile = None
for bf in reversed(bak_files):
    try:
        d = json.loads(open(bf).read())
        cf = d["data"]["Corefile"]
        if "forward . /etc/resolv.conf" in cf:
            backup_corefile = cf
            print(f"  使用备份: {bf}（forward 模式）")
            break
    except Exception:
        continue
if not backup_corefile:
    print("  ❌ 没找到含 forward 的备份！"); raise SystemExit(1)

# 以【当前】CM 为基底（保留当前 metadata），只替换 data.Corefile
cur = json.loads(kcmd("get", "cm", "coredns", "-n", "kube-system", "-o", "json").stdout)
cur["data"]["Corefile"] = backup_corefile
json.dump(cur, open("/tmp/coredns-restore.json", "w"), ensure_ascii=False)
r = kcmd("apply", "--force-conflicts", "-f", "/tmp/coredns-restore.json")
print("  apply:", (r.stdout or r.stderr).strip())

print("")
print("===== 重启 coredns =====")
kcmd("rollout", "restart", "deploy", "coredns", "-n", "kube-system")
subprocess.run(["kubectl","-n","kube-system","rollout","status","deploy/coredns","--timeout=180s"],
               capture_output=True, text=True)
print("  rollout 完成")

print("")
print("===== 验证 1：集群内部 DNS（起 Pod 实测）=====")
time.sleep(20)
r = kcmd("run", "dv2", "-n", "default", "--rm", "-i", "--restart=Never",
         "--image=harbor.wuxing.local/library/nginx:1.27-alpine", "--command", "--",
         "sh", "-c",
         "getent hosts kubernetes.default.svc.cluster.local && echo CLUSTER_OK; "
         "getent hosts loki-0.logging.svc.cluster.local && echo LOKI_OK; "
         "getent hosts www.baidu.com || echo '外部域名快速失败（预期）'")
print((r.stdout or "").strip()[:400])
r = kcmd("delete", "pod", "dv2", "-n", "default", "--force", "--grace-period=0")

print("")
print("===== 验证 2：Loki 数据源连通（Grafana 插件报错的直接原因）=====")
r = kcmd("exec", "-n", "logging", "loki-0", "-c", "loki", "--",
         "wget", "-q", "-O-", "-T", "5",
         "http://prometheus-stack-grafana.monitoring.svc.cluster.local/api/health")
print("  Grafana API:", (r.stdout or "").strip()[:60] or "(失败)")
r = kcmd("exec", "-n", "logging", "loki-0", "-c", "loki", "--",
         "wget", "-q", "-O-", "-T", "5", "--header", "Host: grafana.wuxing.local",
         "http://prometheus-stack-grafana.monitoring.svc.cluster.local:80/api/datasources")
print("  数据源列表(截取):", (r.stdout or "").strip()[:120] or "(失败)")

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