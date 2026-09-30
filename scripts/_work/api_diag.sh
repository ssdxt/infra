#!/bin/bash
echo "########## 1. /deploy/cc 目录结构 ##########"
ls -la /deploy/cc/ 2>&1
echo
echo "--- /deploy/cc/bash/ ---"
ls -la /deploy/cc/bash/ 2>&1
echo
echo "--- /deploy/cc/service/ ---"
ls -la /deploy/cc/service/ 2>&1

echo
echo "########## 2. api_start.sh 是否存在 ##########"
ls -la /deploy/cc/bash/api_start.sh 2>&1
echo "--- 内容 ---"
cat /deploy/cc/bash/api_start.sh 2>&1 | head -40

echo
echo "########## 3. 相关的 systemd 服务 ##########"
systemctl list-unit-files 2>/dev/null | grep -iE "chat_doc|api|web|speech" || echo "  无"
echo
ls -la /etc/systemd/system/ 2>/dev/null | grep -iE "chat|doc|api|web|speech"

echo
echo "########## 4. 服务状态 ##########"
for s in chat_doc_api chat_doc_web chat_doc_speech; do
  echo "===== $s ====="
  systemctl status $s --no-pager 2>&1 | head -12
  echo
done

echo
echo "########## 5. 服务依赖与 ExecStart ##########"
for s in chat_doc_api chat_doc_web chat_doc_speech; do
  if systemctl cat $s >/dev/null 2>&1; then
    echo "===== $s ====="
    systemctl cat $s 2>/dev/null | grep -vE "^\s*#|^\s*$"
    echo "--- RequiresMountsFor ---"
    systemctl show $s -p RequiresMountsFor -p After 2>/dev/null | head -2
    echo
  fi
done

echo
echo "########## 6. 本次启动的失败日志 ##########"
journalctl -b --no-pager -o short-iso 2>/dev/null | grep -iE "api_start|web_start|speech|chat_doc" | head -30
