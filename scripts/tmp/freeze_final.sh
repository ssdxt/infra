#!/bin/bash
echo "########## A. 当前 dmesg 全量里的报错/异常 ##########"
sudo dmesg -T 2>/dev/null | grep -aiE 'error|fail|BUG|WARNING|call trace|pcie|aer|timeout|reset|drvdev|davinci|ascend|nvme|abort' | grep -aviE 'cma_alloc|parport|phytnet_led' | tail -30

echo
echo "########## B. 上一次猝死前后(09:24-09:27) 全部 syslog ##########"
sudo grep -aE '^Sep 14 09:2[4-7]:' /var/log/syslog 2>/dev/null | grep -avE 'kylin-software-center|uksc|synchrodata' | tail -45 | cut -c1-165

echo
echo "########## C. 昇腾日志/转储工具是否有记录 ##########"
sudo ls -la --time-style=full-iso /var/log/nputools_LOG_INFO.log /var/log/ascend_seclog/ 2>/dev/null | head -12
echo "--- nputools 日志最后 15 行 ---"
sudo tail -15 /var/log/nputools_LOG_INFO.log 2>/dev/null | cut -c1-160
echo "--- asc_dumper 是什么（09:10-09:26 出现 36 次）---"
sudo grep -aE '^Sep 14 09:(1[0-9]|2[0-6]):' /var/log/syslog 2>/dev/null | grep -a 'asc_dumper' | tail -8 | cut -c1-170

echo
echo "########## D. NPU 驱动安装/固件时间线（判断与猝死起始时间的相关性）##########"
sudo ls -la --time-style=full-iso /usr/local/Ascend/driver/version.info 2>/dev/null
sudo stat -c '%y %n' /lib/modules/$(uname -r)/updates/davinci_ascend.ko 2>/dev/null
sudo find /lib/modules -name '*davinci*' -o -name '*drv_devdrv*' 2>/dev/null | head -5 | while read f; do sudo stat -c '%y %n' "$f"; done
echo "--- /var/log/ascend_seclog 全部 ---"
sudo ls -la --time-style=full-iso /var/log/ascend_seclog/ 2>/dev/null

echo
echo "########## E. 异常的 kylin-software-center 重启风暴 ##########"
echo "本周期重启计数: $(sudo journalctl -b --no-pager 2>/dev/null | grep -ac 'kylin-software-center.service: Scheduled restart')"
echo "上一个完整周期的重启计数可从 08:26 前的日志看出（restart counter is at N）:"
sudo grep -aoE 'kylin-software-center.service: Scheduled restart job, restart counter is at [0-9]+' /var/log/syslog 2>/dev/null | tail -3

echo
echo "########## F. 是否有 SMART / 温度告警 ##########"
sudo grep -aiE 'smartd|temperature|thermal' /var/log/syslog 2>/dev/null | tail -8 | cut -c1-160
