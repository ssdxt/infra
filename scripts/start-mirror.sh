#!/bin/bash
cd /mnt/e/ZP-工作信息/infra-tool-ssdxt/kubernetes/kubekey/oneclick/offline/image-mirror
chmod +x mirror.sh
nohup bash mirror.sh all > /tmp/mirror-run.log 2>&1 &
echo "已在后台启动，PID=$!"
sleep 25
echo "=== 25 秒后的进度 ==="
tail -8 /tmp/mirror-run.log 2>/dev/null