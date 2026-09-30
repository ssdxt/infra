#!/bin/bash
echo '== find install dir =='
D=$(find / -maxdepth 5 -name 'NVIDIA-Linux-x86_64-550.163.01.run' 2>/dev/null | grep -vE '^/(proc|sys|dev)' | head -1)
echo "dir: $D"
if [ -n "$D" ]; then
  DIR=$(dirname "$D")
  echo "== content of $DIR =="
  ls -la "$DIR" | head -20
  echo '== x86_64.sh head =='
  head -50 "$DIR/x86_64.sh" 2>/dev/null
  echo '== 离线安装 dir =='
  ls -la "$DIR/docker-x86离线安装" 2>/dev/null | head -15
fi
