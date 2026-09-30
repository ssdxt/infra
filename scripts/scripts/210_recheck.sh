#!/bin/bash
echo '== 最新 aiserver 日志(15行) =='
tail -15 /ManualAI/OmniKnow/logs/aiserver.log 2>/dev/null | sed -e 's/\x1b\[[0-9;]*m//g'
echo
echo '== 最近的文档任务成败 =='
grep -aE '任务 .*已标记为失败|任务 .*已完成|文件解析|上传文件|task.*fail' /ManualAI/OmniKnow/logs/aiserver.log 2>/dev/null | sed -e 's/\x1b\[[0-9;]*m//g' | tail -12
echo
echo '== parser 最新(10行) =='
tail -10 /ManualAI/OmniKnow/logs/parser.log 2>/dev/null | sed -e 's/\x1b\[[0-9;]*m//g'
echo
echo '== nginx 日志文件清单 =='
ls -la /ManualAI/OmniKnow/data/nginx/logs/ | tail -10
