#!/bin/bash
echo '== ai_server 容器环境里的 OSS ====='
docker inspect ai_server --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | grep -iE 'OSS|DATABASE_HOST|REDIS_HOST' 
echo '== fixed.yml server-api environment 段 ====='
awk '/^  server-api:/,/^  celery-worker:/' /ManualAI/OmniKnow/docker-omniknow-fixed.yml 2>/dev/null | grep -nE 'environment|OSS|DATABASE|REDIS|ENV_' | head -20
