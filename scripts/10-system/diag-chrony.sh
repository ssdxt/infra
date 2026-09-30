#!/bin/bash
echo "===== 对比：成功节点(.10) vs 失败节点(.19) vs 服务器(.14) ====="
for ip in 10.100.10.10 10.100.10.19 10.100.10.14; do
  echo ""
  echo "########## $ip ##########"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=8 root@$ip '
    echo "  --- chronyd 实际读的配置文件（从进程命令行看）"
    ps -eo args | grep -E "chronyd" | grep -v grep | head -2 | sed "s/^/      /"
    echo "  --- /etc/chrony/ 目录内容"
    ls -la /etc/chrony/ 2>/dev/null | sed "s/^/      /"
    echo "  --- 是否存在 /etc/chrony.conf"
    ls -la /etc/chrony.conf 2>/dev/null | sed "s/^/      /" || echo "      不存在"
    echo "  --- conf.d / sources.d 目录"
    ls -la /etc/chrony/conf.d/ /etc/chrony/sources.d/ 2>/dev/null | sed "s/^/      /"
    echo "  --- 主配置文件里的 server/pool/allow/local 行"
    grep -nE "^\s*(server|pool|allow|local|sourcedir|confdir)" /etc/chrony/chrony.conf 2>/dev/null | sed "s/^/      /"
    echo "  --- 有没有 include 其他文件"
    grep -nE "^\s*(include|confdir|sourcedir)" /etc/chrony/chrony.conf /etc/chrony.conf 2>/dev/null | sed "s/^/      /"
    echo "  --- chronyc sources 完整输出"
    chronyc sources 2>&1 | sed "s/^/      /"
    echo "  --- chronyc activity / 配置源列表"
    chronyc sources -a 2>/dev/null | sed "s/^/      /" || true
    echo "  --- chronyd 版本"
    chronyd --version 2>&1 | head -1 | sed "s/^/      /"
    echo "  --- journal 里 chrony 最近的报错"
    journalctl -u chrony -u chronyd --no-pager -n 8 2>/dev/null | tail -8 | sed "s/^/      /"
  ' 2>/dev/null
done
echo ""
echo "===== 备份文件是否生成（确认脚本确实改了文件）====="
for ip in 10.100.10.10 10.100.10.19 10.100.10.33; do
  echo -n "  [$ip] "; ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=6 root@$ip \
    'ls -la /etc/chrony/chrony.conf.bak.* 2>/dev/null | tail -1; grep -c "10.100.10.14" /etc/chrony/chrony.conf 2>/dev/null | sed "s/^/含10.100.10.14行数=/"; grep -n "server" /etc/chrony/chrony.conf 2>/dev/null | head -3' 2>/dev/null
done