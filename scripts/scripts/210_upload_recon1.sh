#!/bin/bash
echo '===== 关键容器状态（含 mineru） ====='
docker ps -a --format '{{.Names}} | {{.Image}} | {{.Status}}' 2>/dev/null | grep -iE 'mineru|parser|img|server-api|assistant' 
echo
echo '===== 宿主日志目录 ====='
ls -la /ManualAI/OmniKnow/logs/ 2>/dev/null | head -25
echo
echo '===== aiserver.log 尾部 ====='
tail -30 /ManualAI/OmniKnow/logs/aiserver.log 2>/dev/null
echo
echo '===== parser.log 尾部 ====='
tail -15 /ManualAI/OmniKnow/logs/parser.log 2>/dev/null
