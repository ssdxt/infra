#!/bin/bash
WORK=/tmp/wxq-recover
rm -rf "$WORK"; mkdir -p "$WORK"
tar xzf /data1/wxq-monitor.tar.gz -C "$WORK" wxq-plant01-monitor/docker-compose.yaml
echo "===== ARCHIVED docker-compose.yaml (2026-09-24) ====="
cat -n "$WORK/wxq-plant01-monitor/docker-compose.yaml"
echo
echo "===== does archive compose match RUNNING containers? container_name check ====="
echo "--- running container_names:"
docker ps -a --format '{{.Names}}' | grep -i wxq | sort
echo "--- names declared in archived compose:"
grep -E 'container_name|^  [a-z-]+:' "$WORK/wxq-plant01-monitor/docker-compose.yaml"
echo
echo "===== diff archived compose vs the -exporter copy (for context) ====="
diff "$WORK/wxq-plant01-monitor/docker-compose.yaml" /data1/apps/wxq-plant01-monitor/docker-compose.yaml-exporter
echo "(diff exit=$?)"
