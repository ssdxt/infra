#!/usr/bin/env python3
import json, subprocess

def kcmd(*args):
    return subprocess.run(["kubectl", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")

def dnstest(pod_name, server, name):
    r = kcmd("run", pod_name, "-n", "default", "--rm", "-i", "--restart=Never",
             "--image=harbor.wuxing.local/library/nginx:1.27-alpine", "--command", "--",
             "sh", "-c", f"nslookup {name} {server} 2>&1 | tail -4")
    return (r.stdout or "").strip()

def podip(label_ns, label):
    r = kcmd("get", "pods", "-n", label_ns, "-l", label, "-o", "json")
    try:
        d = json.loads(r.stdout)
        return d["items"][0]["status"]["podIP"]
    except Exception:
        return None

print("===== 分层定位：cluster.local 的 NXDOMAIN 来自哪一层 =====")
kdns_ip = kcmd("get", "svc", "-n", "kube-system", "kube-dns", "-o", "jsonpath={.spec.clusterIP}").stdout.strip()
cdns_ip = podip("kube-system", "k8s-app=kube-dns")
nodelocal_ip = "169.254.25.10"
print(f"  kube-dns ClusterIP: {kdns_ip}")
print(f"  coredns Pod IP: {cdns_ip}")
print(f"  nodelocaldns: {nodelocal_ip}")
NAME = "kubernetes.default.svc.cluster.local"

print("")
print("  [1] 直接查 kube-dns ClusterIP:")
print("  " + dnstest("dd1", kdns_ip, NAME).replace("\n", "\n  "))
print("  [2] 直接查 coredns Pod IP:")
if cdns_ip: print("  " + dnstest("dd2", cdns_ip, NAME).replace("\n", "\n  "))
print("  [3] 直接查 nodelocaldns:")
print("  " + dnstest("dd3", nodelocal_ip, NAME).replace("\n", "\n  "))

print("")
print("===== CoreDNS Pod 内直接测试（绕过网络）=====")
r = kcmd("exec", "-n", "kube-system", f"$(kubectl -n kube-system get pods -l k8s-app=kube-dns -o jsonpath='{{.items[0].metadata.name}}')",
         "--", "sh", "-c", "nslookup kubernetes.default.svc.cluster.local 127.0.0.1:53 2>&1 | tail -4")
print((r.stdout or "").strip() or (r.stderr or "").strip())
print("")
print("===== nodelocaldns Pod 日志尾部（找 NXDOMAIN 线索）====="
      )
POD = kcmd("get", "pods", "-n", "kube-system", "-l", "k8s-app=nodelocaldns", "-o", "jsonpath={.items[0].metadata.name}").stdout.strip()
r = kcmd("logs", "-n", "kube-system", POD, "--tail=10")
print((r.stdout or "").strip()[:500])
print("")
print("===== Corefile 现状（nodelocaldns 的 cluster 池）====="
      )
r = kcmd("get", "cm", "nodelocaldns", "-n", "kube-system", "-o", "jsonpath={.data.Corefile}")
print((r.stdout or "")[:600])
