#!/bin/bash
echo "===== docker-compose.yaml (prometheus service section) ====="
cat -n /data1/apps/wxq-plant01-monitor/docker-compose.yaml
echo
echo "===== .env (secrets masked) ====="
sed -E 's/(PASS|TOKEN|SECRET|WEBHOOK|KEY)[A-Z_]*=.*/\1***=MASKED/I' /data1/apps/wxq-plant01-monitor/.env
echo
echo "===== alertmanager config ====="
find /data1/apps/wxq-plant01-monitor/alertmanager -type f | head -20
echo "--- alertmanager.yml:"
cat -n /data1/apps/wxq-plant01-monitor/alertmanager/alertmanager.yml 2>&1
echo
echo "===== prometheusalert dir ====="
ls -la /data1/apps/wxq-plant01-monitor/prometheusalert/
echo
echo "===== backup.sh / restore.sh ====="
cat -n /data1/apps/wxq-plant01-monitor/backup.sh
echo "--- restore.sh:"
cat -n /data1/apps/wxq-plant01-monitor/restore.sh
echo
echo "===== docker compose version ====="
docker compose version 2>&1
docker-compose version 2>&1 | head -2
echo
echo "===== rule_files glob check: are *.yaml files loaded? ====="
grep -n 'rule_files' -A4 /data1/apps/wxq-plant01-monitor/prometheus/prometheus.yml
echo
echo "===== current rules loaded by plant01 prometheus ====="
curl -s http://localhost:9091/api/v1/rules 2>&1 | grep -o '"name":"[^"]*"' | sort -u | head -60
echo
echo "===== count of rule groups / health ====="
curl -s http://localhost:9091/api/v1/rules 2>&1 | grep -o '"health":"[a-z]*"' | sort | uniq -c
echo
echo "===== k8s-federation.yml rules (existing k8s federated rules?) ====="
cat -n /data1/apps/wxq-plant01-monitor/prometheus/rules/k8s-federation.yml
echo
echo "===== federation target ====="
cat -n /data1/apps/wxq-plant01-monitor/prometheus/targets/federation.yaml
