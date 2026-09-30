#!/bin/bash
echo '===== server/.env 完整(实际生效) ====='
cat /ManualAI/OmniKnow/omniknow2/server/.env 2>/dev/null
echo
echo '===== parser 启动脚本 cwd ====='
head -12 /ManualAI/OmniKnow/bash/start_parser.sh 2>/dev/null
echo
echo '===== assistant conf.yaml 里 db/redis 段 ====='
grep -niE 'mysql|redis|host|port|password|database|3306|6379' /ManualAI/OmniKnow/omniknow2/assistant/conf.yaml 2>/dev/null | head -20
echo
echo '===== envs/.env-server（疑似旧模板,对照用） ====='
grep -iE 'DATABASE|REDIS|PASSWORD' /ManualAI/OmniKnow/omniknow2/envs/.env-server 2>/dev/null | sed -E 's/(PASSWORD=).*/\1***/' | head -12
