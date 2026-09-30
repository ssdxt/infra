#!/bin/bash
# 三个待办：A adapter CPU limit  B remoteWrite 固化检查  C plant01 磁盘水位告警
set -u
export KUBECONFIG=/etc/kubernetes/admin.conf

echo "########## A. prometheus-adapter CPU limit 放开 ##########"
kubectl -n monitoring set resources deploy/prometheus-adapter --containers=adapter \
  --limits=cpu=1 --requests=cpu=250m 2>&1 | tail -1
python3 - <<'PY'
try:
    import yaml
    p = "/data1/ssdxt/values/prometheus-adapter-values.yaml"
    d = yaml.safe_load(open(p))
    r = d.setdefault("resources", {})
    r.setdefault("limits", {})["cpu"] = "1"
    rq = r.setdefault("requests", {})
    rq.setdefault("cpu", "250m"); rq.setdefault("memory", "256Mi")
    open(p, "w").write(yaml.safe_dump(d, sort_keys=False, allow_unicode=True))
    print("  ✅ values 已同步 resources.limits.cpu=1")
except ImportError:
    print("  ⚠️ 无 PyYAML：values 未自动改，下次 helm upgrade 前手工把 resources.limits.cpu 设为 '1'")
except Exception as e:
    print("  ⚠️ values 处理失败:", e)
PY
kubectl -n monitoring rollout status deploy/prometheus-adapter --timeout=180s 2>&1 | tail -1
sleep 5
echo -n "  限流是否缓解（近 2 分钟 throttled 速率）: "
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- \
  wget -qO- 'http://localhost:9090/api/v1/query?query=sum(rate(container_cpu_cfs_throttled_periods_total%7Bpod%3D~%22prometheus-adapter.*%22%7D%5B2m%5D))' 2>/dev/null | head -c 120; echo
echo ""

echo "########## B. remoteWrite 持久化检查 ##########"
if grep -qE "max_shards|queueConfig" /data1/ssdxt/monitoring/02-remote-write.sh 2>/dev/null; then
  echo "  ✅ queueConfig patch 已脚本化在 02-remote-write.sh"
  echo "     规矩：每次 helm upgrade prometheus-stack 之后，重跑 bash /data1/ssdxt/monitoring/02-remote-write.sh"
else
  echo "  ⚠️ 02 脚本里没有 queueConfig patch，需补写"
fi
echo ""

echo "########## C. plant01 磁盘水位告警 ##########"
ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=8 root@10.100.10.29 '
cat > /data1/apps/wxq-plant01-monitor/prometheus/rules/disk-watermark.yml <<"EOF"
groups:
- name: disk-watermark
  rules:
  - alert: Plant01DataDiskSpaceLow
    expr: (node_filesystem_avail_bytes{fstype!~"tmpfs|overlay|squashfs"} / node_filesystem_size_bytes{fstype!~"tmpfs|overlay|squashfs"}) * 100 < 15
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "磁盘剩余不足15% ({{ $labels.instance }} {{ $labels.mountpoint }})"
      description: "挂载点 {{ $labels.mountpoint }} 剩余 {{ $value | printf \"%.1f\" }}%"
  - alert: Plant01PrometheusStorageNearLimit
    expr: prometheus_tsdb_storage_blocks_bytes > 21474836480
    for: 15m
    labels:
      severity: warning
    annotations:
      summary: "Prometheus TSDB 已超 20GB（retention.size=25GB 的 80%），即将开始逐出数据"
EOF
echo "  规则文件已写入: disk-watermark.yml"
curl -s -X POST http://localhost:9091/-/reload >/dev/null 2>&1 && echo "  ✅ 已热加载 prometheus（无需重启容器）"
sleep 3
echo -n "  规则加载数: "
curl -s http://localhost:9091/api/v1/rules 2>/dev/null | grep -o "Plant01DataDiskSpaceLow\|Plant01PrometheusStorageNearLimit" | sort -u | wc -l
'
echo ""
echo "########## 完成 ##########"