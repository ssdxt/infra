#!/bin/bash
cd /data1/apps/wxq-plant01-monitor
echo "===== A. docker-compose.yaml-exporter ====="
cat -n docker-compose.yaml-exporter
echo
echo "===== B. exporter/docker-compose.yaml ====="
cat -n exporter/docker-compose.yaml
echo
echo "===== C. any compose-like backups anywhere on disk ====="
find / -xdev \( -name 'docker-compose*.yaml*' -o -name 'docker-compose*.yml*' -o -name 'compose.yaml*' \) 2>/dev/null | grep -v '^/proc' | head -60
echo
echo "===== D. backups dirs / tar of config ====="
ls -la /data1/apps/wxq-plant01-monitor/backups 2>&1 | head
find /data1 /root /home -maxdepth 4 -name 'config.tar.gz' -o -maxdepth 4 -name '*.tar.gz' 2>/dev/null | grep -i -E 'wxq|monitor|backup' | head -30
echo
echo "===== E. tools dir ====="
ls -la tools/
echo
echo "===== F. shell history mentioning docker-compose.yaml ====="
for f in /root/.bash_history /home/ubuntu/.bash_history; do echo "--- $f"; grep -n -E 'compose|mv |rm ' "$f" 2>/dev/null | tail -40; done
echo
echo "===== G. promtool available in prometheus container? ====="
docker exec wxq-prometheus promtool --version 2>&1 | head -3
echo
echo "===== H. container env for each wxq service (for compose reconstruction) ====="
for c in wxq-prometheus wxq-alertmanager wxq-prometheusalert wxq-process-exporter wxq-grafana wxq-victoriametrics wxq-node-exporter wxq-blackbox wxq-otel wxq-pushgateway; do
  echo "--- $c"
  docker inspect "$c" --format '{{.Config.Image}}'
  docker inspect "$c" --format 'Labels: {{json .Config.Labels}}' | tr ',' '\n' | grep -E 'compose.(service|project|container-number|oneoff|depends_on|config-hash)' | tr '\n' ' '; echo
done
