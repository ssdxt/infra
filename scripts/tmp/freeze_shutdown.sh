#!/bin/bash
echo "########## A. 09:09 与 09:26 两次关机的完整关机序列 ##########"
for t in '09:0[6-9]' '09:2[0-9]'; do
  echo "==================== 时间窗 $t ===================="
  sudo grep -aE "^Sep 14 $t:" /var/log/syslog 2>/dev/null | grep -aiE 'systemd\[1\]|shutdown|power|reboot|halt|suspend|sleep|hibernat|watchdog|emergency|rescue' | tail -35
done

echo
echo "########## B. journal 本周期里是否有 suspend/电源键/关机事件 ##########"
sudo journalctl -b --no-pager 2>&1 | grep -aiE 'suspend|hibernat|power key|powerkey|Sleep|shutdown|reboot|Reached target' | tail -20

echo
echo "########## C. 是否有 systemd 的关机记录（wtmp 精确时间）##########"
last -x -F -n 20 reboot shutdown runlevel 2>/dev/null | head -25

echo
echo "########## D. 09:10-09:26 之间（17 分钟运行期）syslog 的高频/异常来源统计 ##########"
sudo grep -aE '^Sep 14 09:(1[0-9]|2[0-6]):' /var/log/syslog 2>/dev/null | \
  awk '{print $5}' | sed 's/\[[0-9]*\]//' | sort | uniq -c | sort -rn | head -15
echo "--- 该区间内的报错行 ---"
sudo grep -aE '^Sep 14 09:(1[0-9]|2[0-6]):' /var/log/syslog 2>/dev/null | grep -aiE 'error|fail|crash|coredump|dump|panic|BUG|segfault|timeout' | tail -20

echo
echo "########## E. 08:32-09:08 运行期（36 分钟）最后的 30 行 ##########"
sudo grep -aE '^Sep 14 09:0[0-8]:' /var/log/syslog 2>/dev/null | tail -30 | cut -c1-160
