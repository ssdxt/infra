#!/bin/bash
echo "=== /data/aippt/api 目录 ==="
ls -la /data/aippt/api/ 2>&1
echo "=== /data/aippt/agent 目录 ==="
ls -la /data/aippt/agent/ 2>&1
echo
echo "=== api-config.yaml 中的 IP/端口引用 ==="
grep -n -E '18\.18\.18\.60|127\.0\.0\.1|localhost|host\.docker|36379|38848|33306|nacos|redis|mysql' /data/aippt/api/api-config.yaml 2>/dev/null | head -40
echo
echo "=== agent-config.yaml 中的 IP/端口引用 ==="
grep -n -E '18\.18\.18\.60|127\.0\.0\.1|localhost|host\.docker|36379|38848|33306|nacos|redis|mysql' /data/aippt/agent/agent-config.yaml 2>/dev/null | head -40
echo
echo "=== aippt_init.sh 内容 (前60行) ==="
head -60 /data/aippt/aippt_init.sh 2>/dev/null
echo
echo "=== 镜像默认 config.yaml 的 redis/nacos 段 ==="
sed -n '45,75p' /tmp/api_configs/config.yaml 2>/dev/null
sed -n '320,340p' /tmp/api_configs/config.yaml 2>/dev/null
