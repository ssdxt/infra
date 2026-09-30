#!/bin/bash
echo "=== 1panel 服务状态 ==="
systemctl status 1panel --no-pager -l 2>&1 | head -8
echo "=== 1panel 进程 ==="
ps aux | grep -i 1panel | grep -v grep | head -5
echo "=== /opt/1panel 目录结构 ==="
ls -la /opt/1panel/
echo "=== 1panel db 目录 ==="
ls -la /opt/1panel/1panel/db/ 2>/dev/null
echo "=== 1pctl 命令 ==="
which 1pctl
1pctl 2>&1 | head -25
echo "=== 面板监听端口 ==="
ss -tlnp 2>/dev/null | grep -E '9999|1panel|:80 |:443 '
echo "=== sqlite3 是否可用 ==="
which sqlite3
echo "=== 尝试读取用户表 ==="
sqlite3 /opt/1panel/1panel/db/1Panel.db ".tables" 2>&1
echo "--- users 表 ---"
sqlite3 /opt/1panel/1panel/db/1Panel.db "select id,username,email,role,status from users;" 2>&1
echo "=== conf 目录 ==="
ls /opt/1panel/1panel/conf/ 2>/dev/null
