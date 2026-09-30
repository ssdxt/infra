#!/bin/bash
echo "########## A. 开机慢 16 秒的原因：systemd 超时/等待 ##########"
sudo journalctl -b --no-pager 2>&1 | grep -aiE 'timed out|timeout|waiting for|Job .* failed|start-limit' | head -20
echo "--- 09:09 那次开机（44s）对比 ---"
sudo grep -aE '^Sep 14 09:(0[9]|1[0-9]):' /var/log/syslog 2>/dev/null | grep -aiE 'timed out|timeout|waiting for|start-limit|Job ' | head -15

echo
echo "########## B. FanCtrl 相关 ##########"
echo "--- /etc/fan_config.json ---"
sudo cat /etc/fan_config.json 2>&1
echo "--- FanStat ---"
sudo ls -la /usr/local/bin/FanStat 2>/dev/null
echo "--- 进程是否在跑 ---"
ps aux | grep -iE 'FanCtrl|FanStat' | grep -v grep
echo "--- 它读的 DCMI 温度（用 npu-smi 对照）---"
sudo npu-smi info -t temp -i 24 -c 0 2>&1 | head -8

echo
echo "########## C. 是否有 suspend/hibernate 参与 ##########"
sudo journalctl -b --no-pager 2>&1 | grep -aiE 'suspend|hibernat|freeze|sleep' | head -10
echo "--- systemd 的 sleep/suspend 目标 ---"
systemctl list-units --type=target --no-pager 2>/dev/null | grep -iE 'sleep|suspend'

echo
echo "########## D. 内核 cmdline 与 watchdog ##########"
cat /proc/cmdline
echo "nmi_watchdog=$(cat /proc/sys/kernel/nmi_watchdog 2>/dev/null)  watchdog_thresh=$(cat /proc/sys/kernel/watchdog_thresh 2>/dev/null)"
echo "--- 硬件 watchdog 设备 ---"
ls -la /dev/watchdog* 2>/dev/null || echo "无 /dev/watchdog"

echo
echo "########## E. 卡死前是否有 NPU/其他设备的 AER 或 PCIe 错误 ##########"
sudo grep -aiE 'aer|pcie.*error|corrected|uncorrectable|link down|surprise' /var/log/kern.log /var/log/syslog 2>/dev/null | grep -aviE 'Modules linked|drv_pcie' | tail -15
echo "(空 = 无 PCIe AER 错误记录)"
