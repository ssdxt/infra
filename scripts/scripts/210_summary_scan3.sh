#!/bin/bash
echo '===== start_main.sh (ai_server) ====='
head -40 /ManualAI/OmniKnow/bash/start_main.sh 2>/dev/null
echo
echo '===== start_assistant.sh ====='
head -30 /ManualAI/OmniKnow/bash/start_assistant.sh 2>/dev/null
echo
echo '===== omniknow2/server/docker-compose.yaml env 用法 ====='
grep -nE 'env_file|environment|container_name|image|command|\.env' /ManualAI/OmniKnow/omniknow2/server/docker-compose.yaml 2>/dev/null | head -15
echo
echo '===== 运行中 ai_server 进程 cwd 与 .env 定位 ====='
docker exec ai_server sh -c 'ls -la /proc/1/cwd 2>/dev/null; ls /ManualAI/OmniKnow/omniknow2/server/.env /ManualAI/OmniKnow/omniknow2/envs/.env-server 2>/dev/null' 2>/dev/null
echo
echo '===== 实际连通性: ai_server → cc-mysql / cc-redis ====='
docker exec ai_server sh -c 'getent hosts cc-mysql cc-redis 2>/dev/null' 2>/dev/null
