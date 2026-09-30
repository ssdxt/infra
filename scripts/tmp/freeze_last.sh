#!/bin/bash
echo "############ 各运行期最后一条日志（判定猝死 vs 正常关机）############"
for w in "08:1[0-9]|08:2[0-9]|08:3[01]" "08:3[3-9]|08:4[0-9]|08:5[0-9]|09:0[0-8]" "09:1[0-9]|09:2[0-6]"; do
  echo "==================== 窗口: $w ===================="
  sudo grep -aE "^Sep 14 ($w):" /var/log/syslog 2>/dev/null | tail -6 | cut -c1-170
  echo
done

echo "############ 三个窗口的行数与首末时间 ############"
for w in "08:1[0-9]|08:2[0-9]|08:3[01]" "08:3[3-9]|08:4[0-9]|08:5[0-9]|09:0[0-8]" "09:1[0-9]|09:2[0-6]"; do
  echo "--- $w ---"
  sudo grep -aE "^Sep 14 ($w):" /var/log/syslog 2>/dev/null | head -1 | cut -c1-100
  sudo grep -aE "^Sep 14 ($w):" /var/log/syslog 2>/dev/null | tail -1 | cut -c1-100
  echo "行数: $(sudo grep -acE "^Sep 14 ($w):" /var/log/syslog 2>/dev/null)"
done

echo
echo "############ 08:32 前那次(case1)与 09:26 前那次(case3) 是否含关机序列 ############"
for w in "08:2[5-9]|08:3[01]" "09:2[0-6]"; do
  echo "==================== $w ===================="
  echo "关机类行数: $(sudo grep -aE "^Sep 14 ($w):" /var/log/syslog 2>/dev/null | grep -aciE 'Stopping|Stopped target|Reached target Shutdown|Unmounting|systemd-shutdown|Rebooting|Powering off|halt')"
  echo "--- 这些关机行 ---"
  sudo grep -aE "^Sep 14 ($w):" /var/log/syslog 2>/dev/null | grep -aiE 'Stopping|Stopped target|Reached target Shutdown|Unmounting|systemd-shutdown|Rebooting|Powering off' | tail -10 | cut -c1-150
done
