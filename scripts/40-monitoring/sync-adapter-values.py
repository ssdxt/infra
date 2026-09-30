#!/usr/bin/env python3
import yaml, subprocess, sys
p = "/data1/ssdxt/values/prometheus-adapter-values.yaml"
d = yaml.safe_load(open(p))
r = d.setdefault("resources", {})
r.setdefault("limits", {})["memory"] = "2Gi"
r["limits"]["cpu"] = "2"
r.setdefault("requests", {})["memory"] = "512Mi"
r["requests"]["cpu"] = "250m"
open(p, "w").write(yaml.safe_dump(d, sort_keys=False, allow_unicode=True))
print("values 已同步: limits {cpu: 2, memory: 2Gi}, requests {cpu: 250m, memory: 512Mi}")
print("--- 最终 values resources 段:")
print(yaml.dump({"resources": d.get("resources")}, sort_keys=False, allow_unicode=True))
# 实时状态复核
for cmd in [
    "kubectl -n monitoring get pods | grep adapter",
    "kubectl get apiservice v1beta1.custom.metrics.k8s.io -o jsonpath='{.status.conditions[0].type}={.status.conditions[0].status}'",
]:
    out = subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout
    print(out.strip())