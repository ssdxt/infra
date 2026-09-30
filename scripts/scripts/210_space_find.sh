#!/bin/bash
echo '===== space 表结构 ====='
docker exec cc-mysql mysql -uroot -p'Chicheng!234' omniknow -e 'SHOW COLUMNS FROM space;' 2>/dev/null | head -15
echo '===== 所有 space id ====='
docker exec cc-mysql mysql -uroot -p'Chicheng!234' omniknow -e 'SELECT id, name FROM space LIMIT 30;' 2>/dev/null | head -20
echo '===== 日志定位图片上传的 space ====='
grep -nE 'images/|space_image|NoSuchBucket' /ManualAI/OmniKnow/logs/aiserver.log 2>/dev/null | grep -B2 -A2 'NoSuchBucket' | head -10
awk '/NoSuchBucket/{for(i=NR-25;i<=NR;i++) a[i]=$0} END{for(i=1;i<=NR;i++) if(i in a) print a[i]}' /ManualAI/OmniKnow/logs/aiserver.log 2>/dev/null | grep -E 'POST|GET|spaces/|key' | tail -6
