#!/bin/bash
echo '===== 全部空间(uuid) ====='
docker exec cc-mysql mysql -uroot -p'Chicheng!234' omniknow -e 'SELECT uuid, name FROM space;' 2>/dev/null | head -20
echo '===== 报错行 15550 附近的请求 ====='
sed -n '15530,15560p' /ManualAI/OmniKnow/logs/aiserver.log 2>/dev/null | grep -E 'PUT|POST|GET|spaces/|image' | head -8
echo '===== 15733 附近(第二次报错) ====='
sed -n '15715,15745p' /ManualAI/OmniKnow/logs/aiserver.log 2>/dev/null | grep -E 'PUT|POST|GET|spaces/' | head -6
