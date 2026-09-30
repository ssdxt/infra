#!/bin/bash
# 在 plant01 上执行：磁盘水位告警规则（从工作站直接连，支持密码认证）
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
echo "规则文件已写入: /data1/apps/wxq-plant01-monitor/prometheus/rules/disk-watermark.yml"
curl -s -X POST http://localhost:9091/-/reload >/dev/null 2>&1 && echo "✅ prometheus 已热加载"
sleep 3
echo -n "新规则加载数: "
curl -s http://localhost:9091/api/v1/rules 2>/dev/null | grep -o "Plant01DataDiskSpaceLow\|Plant01PrometheusStorageNearLimit" | sort -u | wc -l