#!/bin/bash
echo "########## A. 上一次启动周期(01:12-08:01) syslog 的绝对最后 40 行 ##########"
sudo awk '/^Sep 14 0[6-8]:/ {print}' /var/log/syslog | grep -aE '^Sep 14 0[67]:' | tail -40

echo
echo "########## B. 08:01 之前 10 分钟内 syslog 的所有内容（冻结瞬间业务侧）##########"
sudo awk '/^Sep 14 07:5[0-9]:|^Sep 14 08:0[01]:/ {print}' /var/log/syslog | tail -50

echo
echo "########## C. kern.log 中所有 内核时间 >= 30 秒 的行（启动之后真正运行期的内核消息）##########"
sudo grep -aoE '^Sep 14 [0-9:]+ .*\[ *[0-9]{2,}\.[0-9]+\]' /var/log/kern.log | awk -F'[][]' '{split($2,a,"."); if (a[1]+0 >= 60) print}' | tail -40
echo "(以上为空 = 运行期内核一句都没记录/没落盘)"
