#!/bin/bash
echo "########## A. 磁盘空间 ##########"
df -hT / /boot /deploy /var 2>&1
echo "--- inode ---"
df -i / /var 2>&1 | head -5

echo
echo "########## B. 09:09 卡死前的 kern.log 尾部（最后一次卡死的现场）##########"
echo ">>> kern.log 中 09:0x 的原始行数: $(sudo grep -c '09:0[0-9]:' /var/log/kern.log)"
echo ">>> --- 09:00~09:09 之间 kern.log 全部内容 ---"
sudo awk '/^Sep 14 09:0[0-9]:/ {print}' /var/log/kern.log | tail -60

echo
echo "########## C. 08:32 卡死前的 kern.log（倒数第二次）##########"
sudo awk '/^Sep 14 08:2[0-9]:|^Sep 14 08:3[0-2]:/ {print}' /var/log/kern.log | tail -40

echo
echo "########## D. 上一周期 syslog 最后 60 行（08:32 卡死瞬间，含非内核日志）##########"
sudo awk '/^Sep 14 08:2[5-9]:|^Sep 14 08:3[0-2]:/ {print}' /var/log/syslog | tail -60
