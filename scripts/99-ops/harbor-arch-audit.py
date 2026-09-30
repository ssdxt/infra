#!/usr/bin/env python3
# 检查 Harbor 中各仓库 tag 是多架构列表还是单架构（及具体架构）
import json, ssl, sys, urllib.request, base64

H = "harbor.wuxing.local"
USER = "admin"
PASS = "<HARBOR_PASSWORD>"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

ACCEPT = ", ".join([
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
])


def get(path, accept=ACCEPT):
    req = urllib.request.Request("https://" + H + path)
    req.add_header("Accept", accept)
    tok = base64.b64encode(f"{USER}:{PASS}".encode()).decode()
    req.add_header("Authorization", "Basic " + tok)
    with urllib.request.urlopen(req, context=ctx, timeout=20) as r:
        return r.headers.get("Content-Type", ""), r.read()


def check(repo, tag):
    try:
        ct, body = get(f"/v2/{repo}/manifests/{tag}")
    except Exception as e:
        return f"  {repo}:{tag}  => 读取失败: {e}"
    if "manifest.list" in ct or "image.index" in ct:
        d = json.loads(body)
        plats = []
        for m in d.get("manifests", []):
            p = m.get("platform") or {}
            if p.get("architecture") and p.get("architecture") != "unknown":
                plats.append(f"{p.get('os','?')}/{p.get('architecture','?')}")
        return f"  [多架构] {repo}:{tag}  => {', '.join(sorted(set(plats))) or '(无平台信息)'}"
    # 单架构：取 config blob
    d = json.loads(body)
    cfg = (d.get("config") or {}).get("digest")
    if not cfg:
        return f"  [单架构] {repo}:{tag}  => 无 config digest"
    try:
        _, blob = get(f"/v2/{repo}/blobs/{cfg}")
        c = json.loads(blob)
        return f"  [单架构] {repo}:{tag}  => {c.get('os','?')}/{c.get('architecture','?')}  <<< 只有一种架构"
    except Exception as e:
        return f"  [单架构] {repo}:{tag}  => config 读取失败: {e}"


targets = [
    ("library/nginx", "latest"),
    ("library/haproxy", "latest"),
    ("library/busybox", "1.38.0"),
    ("wxq-monitor/prometheus", "latest"),
    ("wxq-monitor/node-exporter", "latest"),
    ("wxq-monitor/alertmanager", "latest"),
    ("wxq-monitor/blackbox-exporter", "latest"),
    ("wxq-monitor/pushgateway", "latest"),
    ("wxq-monitor/ipmi-exporter", "latest"),
    ("wxq-monitor/process-exporter", "latest"),
    ("wxq-monitor/smartctl-exporter", "latest"),
    ("wxq-monitor/prometheus-alert", "latest"),
    ("wxq-otel/otelcol-contrib", "latest"),
    ("wxq-vm/victoria-metrics", "latest"),
    ("wxq-grafana/grafana", "latest"),
    ("monitoring/prometheus", "v2.54.1"),
    ("monitoring/grafana", "11.2.0"),
    ("monitoring/node-exporter", "v1.8.2"),
    ("monitoring/kube-state-metrics", "v2.13.0"),
    ("monitoring/alertmanager", "v0.27.0"),
    ("monitoring/k8s-sidecar", "1.27.4"),
    ("monitoring/prometheus-operator", "v0.76.1"),
    ("monitoring/prometheus-config-reloader", "v0.76.1"),
    ("cert-manager/cert-manager-controller", "v1.16.1"),
    ("coredns/coredns", "v1.13.1"),
    ("dns/k8s-dns-node-cache", "1.26.7"),
    ("kubernetes/pause", "3.10.2"),
    ("cilium/cilium", "v1.20.1"),
    ("cilium/cilium-envoy", "v1.37.5-1786810558-766ccfb37260a43e9d228837aa84ce3faf9f64e7"),
    ("cilium/operator", "v1.20.1"),
    ("openebs/provisioner-localpv", "4.1.0"),
    ("plndr/kube-vip", "v0.8.9"),
]

print("=== Harbor 仓库架构清单")
for repo, tag in targets:
    print(check(repo, tag))
