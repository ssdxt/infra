#!/bin/bash
echo "########## A. 内存 / swap 当前状态 ##########"
free -h
echo "--- swappiness ---"
cat /proc/sys/vm/swappiness /proc/sys/vm/vfs_cache_pressure /proc/sys/vm/min_free_kbytes 2>/dev/null
echo "--- overcommit ---"
cat /proc/sys/vm/overcommit_memory /proc/sys/vm/overcommit_ratio 2>/dev/null
echo "--- swap 设备 ---"
swapon --show
cat /proc/swaps

echo
echo "########## B. 当前占内存最多的进程 ##########"
ps -eo pid,ppid,rss,vsz,pmem,comm --sort=-rss | head -20
echo "--- cgroup 内存占用前 15 ---"
sudo systemctl status docker --no-pager 2>/dev/null | head -3
sudo docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.CPUPerc}}' 2>&1 | head -15

echo
echo "########## C. syslog 里 stall 是什么 ##########"
sudo grep -aiE 'stall' /var/log/syslog /var/log/kern.log 2>/dev/null | sed 's/.*stall/stall/' | sort | uniq -c | sort -rn | head -10

echo
echo "########## D. syslog 里所有 BUG / WARNING / call trace 记录（按启动周期分布）##########"
sudo grep -anE 'BUG:|Bad page map|Bad swap|cut here|WARNING: CPU|Call trace|bad pte' /var/log/kern.log 2>/dev/null | awk -F: '{print $2}' | cut -c1-15 | sort | uniq -c | sort -rn | head -20

echo
echo "########## E. 09:22 / 09:28 两次 pt_main_thread core 的事件上下文 ##########"
sudo journalctl -b --no-pager 2>&1 | grep -aE 'pt_main_thread|mindie|Out of memory|oom|segfault' | tail -20

echo
echo "########## F. 09:09 那次硬重启前，最后落盘的业务日志时间线 ##########"
sudo ls -la --time-style=full-iso /var/log/syslog* /var/log/kern.log* 2>/dev/null
echo "--- syslog 中 09:0x 的记录（上一次运行到卡死的最后时刻）---"
sudo grep -aE '^Sep 14 09:0[0-9]:' /var/log/syslog 2>/dev/null | tail -30
