#!/bin/bash
echo "== E盘挂载?"
ls /mnt/e/ 2>/dev/null | head -3 || echo no-e-mount
echo "== WSL 反向可达性测试: 从 control-01 访问 WSL"
timeout 6 bash -c "</dev/tcp/10.100.200.159/22" 2>/dev/null && echo "WSL-ssh-reachable" || echo "WSL-not-reachable-from-cluster"
echo "== 拉镜像进度"
tail -5 /home/cc/pull.log 2>/dev/null