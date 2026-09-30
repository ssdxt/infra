#!/bin/bash
cp /mnt/c/Users/CC/Desktop/dsh/image-mirror/mirror.sh ~/mirror.sh
chmod +x ~/mirror.sh
nohup bash ~/mirror.sh all > /tmp/mirror-run.log 2>&1 &
echo "后台启动 PID=$!"
sleep 30
echo "=== 30 秒后进度 ==="
tail -10 /tmp/mirror-run.log 2>/dev/null
echo "=== 已推送成功的镜像 ==="
grep -c "OK$" /tmp/mirror-run.log 2>/dev/null || echo 0