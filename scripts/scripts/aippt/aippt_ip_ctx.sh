#!/bin/bash
echo "=== docker-compose.yml 中 18.18.18.60 上下文 ==="
grep -n -B2 -A2 "18.18.18.60" /data/aippt/docker-compose.yml
echo
echo "=== web/aippt.conf 中 18.18.18.60 上下文 ==="
grep -n -B2 -A2 "18.18.18.60" /data/aippt/web/aippt.conf
echo
echo "=== fc/.env.prod 中 18.18.18.60 上下文 ==="
grep -n -B1 -A1 "18.18.18.60" /data/aippt/fc/.env.prod
echo
echo "=== font/.env.prod 中 18.18.18.60 上下文 ==="
grep -n -B1 -A1 "18.18.18.60" /data/aippt/font/.env.prod
echo
echo "=== agent-config.yaml 前50行(看结构) ==="
head -50 /data/aippt/agent/agent-config.yaml
