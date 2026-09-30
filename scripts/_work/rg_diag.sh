#!/bin/bash
echo "########## 1. 当前 rg 进程 ##########"
ps -eo pid,ppid,etimes,%cpu,%mem,rss,stat,cmd 2>/dev/null | grep "[r]ipgrep-universal" | head -10

echo
echo "########## 2. 负载 ##########"
uptime

echo
echo "########## 3. 每个 rg 的工作目录（它在扫哪里）##########"
for p in $(pgrep -f "ripgrep-universal" 2>/dev/null | head -5); do
  echo "--- PID $p ---"
  echo "  cwd  : $(sudo readlink /proc/$p/cwd 2>&1)"
  echo "  root : $(sudo readlink /proc/$p/root 2>&1)"
  echo "  启动 : $(ps -o lstart= -p $p 2>/dev/null)"
  echo "  CPU时间: $(ps -o time= -p $p 2>/dev/null)"
  echo "  参数根目录(最后一个非 - 开头的参数):"
  sudo tr '\0' '\n' < /proc/$p/cmdline 2>/dev/null | grep -v "^-" | tail -3 | sed 's/^/    /'
done

echo
echo "########## 4. rg 打开的文件/目录（看它卡在哪）##########"
for p in $(pgrep -f "ripgrep-universal" 2>/dev/null | head -2); do
  echo "--- PID $p 打开的 fd 数: $(sudo ls /proc/$p/fd 2>/dev/null | wc -l) ---"
  sudo ls -l /proc/$p/fd 2>/dev/null | awk '{print $NF}' | grep -v "^/dev\|^socket\|^pipe\|^anon" | tail -12
done

echo
echo "########## 5. 父进程链（哪个 VS Code 窗口触发的）##########"
for p in $(pgrep -f "ripgrep-universal" 2>/dev/null | head -2); do
  echo "--- PID $p 的父链 ---"
  q=$p
  for i in 1 2 3 4; do
    q=$(ps -o ppid= -p $q 2>/dev/null | tr -d ' ')
    [ -z "$q" ] || [ "$q" = "0" ] && break
    echo "    $q: $(ps -o cmd= -p $q 2>/dev/null | cut -c1-120)"
  done
done

echo
echo "########## 6. VS Code Server 里的 exclude 配置 ##########"
for f in /home/kzzk/.vscode-server/data/Machine/settings.json \
         /home/kzzk/.vscode-server/data/User/settings.json; do
  echo "--- $f ---"
  sudo cat "$f" 2>/dev/null | head -30 || echo "  (不存在)"
done

echo
echo "########## 7. 磁盘 IO ##########"
which iostat >/dev/null 2>&1 && iostat -x 1 2 2>/dev/null | tail -12 || echo "无 iostat"
cat /proc/loadavg
