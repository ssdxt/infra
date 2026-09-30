#!/bin/bash
echo "########## 0. 是否持久化 journal ##########"
ls -ld /var/log/journal 2>&1
grep -E '^\s*Storage' /etc/systemd/journald.conf 2>/dev/null
echo "--- journal boots ---"
sudo journalctl --list-boots 2>&1 | tail -8

echo
echo "########## 1. 上一次启动周期的 ERROR 级日志（卡死前）##########"
sudo journalctl -b -1 -p err --no-pager 2>&1 | tail -40

echo
echo "########## 2. 上一次启动周期 内核所有 WARNING/ERROR 关键词 ##########"
sudo journalctl -b -1 -k --no-pager 2>&1 | grep -aiE 'panic|oops|BUG:|hung task|blocked for more|soft lockup|hard lockup|watchdog|rcu_sched|stall|out of memory|oom-kill|Killed process|thermal|throttl|mce|Hardware Error|EDAC|I/O error|ata[0-9]|nvme|EXT4-fs error|call trace|Call Trace|devdrv|davinci|ascend|drvdev|pcie|AER' | tail -60
echo "(以上为空 = 上一次启动周期没有任何此类内核日志)"

echo
echo "########## 3. 上一次启动周期最后 80 行内核日志（看卡死瞬间）##########"
sudo journalctl -b -1 -k --no-pager 2>&1 | tail -80
