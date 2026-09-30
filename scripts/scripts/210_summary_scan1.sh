#!/bin/bash
echo '===== 1. /ManualAI 目录树(2层) ====='
find /ManualAI -maxdepth 2 -type d 2>/dev/null | sort | head -40
echo
echo '===== 2. omniknow2 下的 env/配置 ====='
find /ManualAI/OmniKnow/omniknow2 -maxdepth 3 \( -name '.env*' -o -name '*.env' -o -name '*.yml' -o -name '*.yaml' \) 2>/dev/null | sort | head -30
echo
echo '===== 3. 哪些配置文件引用了 mysql/redis ====='
grep -rilE 'mysql|redis|3306|6379|db_host|DB_HOST|REDIS_' /ManualAI/OmniKnow/omniknow2 2>/dev/null | head -20
echo
echo '===== 4. docker-compose.yml: cc-mysql 段 ====='
awk '/^  cc-mysql:|^  mysql:/,/^  [a-z_0-9-]+:/' /ManualAI/OmniKnow/docker-compose.yml 2>/dev/null | head -35
echo '===== 5. docker-compose.yml: cc-redis 段 ====='
awk '/^  cc-redis:|^  redis:/,/^  [a-z_0-9-]+:/' /ManualAI/OmniKnow/docker-compose.yml 2>/dev/null | head -25
echo
echo '===== 6. docker-omniknow-fixed.yml 里 DB/REDIS 引用 ====='
grep -niE 'mysql|redis|3306|6379|DB_|REDIS_|DATABASE' /ManualAI/OmniKnow/docker-omniknow-fixed.yml 2>/dev/null | head -15
