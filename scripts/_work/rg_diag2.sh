#!/bin/bash
echo "########## 1. VS Code 打开的工作区 ##########"
LOGD=$(ls -dt /home/kzzk/.vscode-server/data/logs/*/ 2>/dev/null | head -1)
echo "日志目录: $LOGD"
sudo grep -rhoiE '"workspaceFolder[^,]{0,120}|folderUri[^,]{0,120}|/deploy[a-z0-9_/]*' \
  $LOGD 2>/dev/null | sort -u | head -15

echo
echo "--- remoteagent.log 里的路径 ---"
sudo grep -oiE "(file://)?/[a-zA-Z0-9_./-]{2,60}" $LOGD/remoteagent.log 2>/dev/null | sort | uniq -c | sort -rn | head -12

echo
echo "########## 2. rg 到底在扫什么（采样 3 次）##########"
for i in 1 2 3; do
  p=$(pgrep -f "ripgrep-universal" | head -1)
  [ -z "$p" ] && echo "  rg 已退出" && break
  echo "--- 采样 $i (PID $p, CPU $(ps -o %cpu= -p $p)) ---"
  sudo ls -l /proc/$p/fd 2>/dev/null | awk '{print $NF}' | grep "^/" | grep -vE "vscode-server|/dev/" | head -6
  sleep 2
done

echo
echo "########## 3. /sys 有多少条目（解释为什么扫不完）##########"
echo "/sys 顶层: $(ls /sys 2>/dev/null | wc -l) 项"
echo "/sys/devices: $(find /sys/devices -maxdepth 3 2>/dev/null | wc -l) 项(深度3)"
echo "/sys/bus/i2c/devices: $(ls /sys/bus/i2c/devices 2>/dev/null | wc -l) 项"
echo "符号链接数: $(find /sys -maxdepth 4 -type l 2>/dev/null | wc -l)"

echo
echo "########## 4. 现有的 VS Code 设置文件 ##########"
for f in /home/kzzk/.vscode-server/data/Machine/settings.json \
         /home/kzzk/.vscode-server/data/User/settings.json; do
  if sudo test -f "$f"; then
    echo "--- $f (存在, $(sudo wc -c < $f) 字节) ---"
    sudo cat "$f"
  else
    echo "--- $f (不存在) ---"
  fi
done

echo
echo "########## 5. 当前负载 ##########"
uptime
ps -eo pid,%cpu,etime,cmd 2>/dev/null | grep "[r]ipgrep" | head -3
