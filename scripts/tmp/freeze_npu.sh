#!/bin/bash
echo "########## A. 猝死时刻(09:26:5x)前后 昇腾 plog / 驱动日志 ##########"
for f in /root/ascend/log/debug/plog/plog-*.log /root/ascend/log/run/plog/plog-*.log; do
  [ -e "$f" ] || continue
  echo "--- $f ($(stat -c '%y' "$f" | cut -c1-19)) ---"
  sudo grep -aiE '\[ERROR\]|\[EVENT\]|errorStr|exception|reset|timeout|drvdev|fault' "$f" 2>/dev/null | tail -8 | cut -c1-190
done 2>/dev/null | tail -50

echo
echo "########## B. 猝死时刻的 device 侧日志 ##########"
sudo ls -la --time-style=+%H:%M:%S /root/ascend/log/ 2>/dev/null
sudo find /root/ascend/log -name '*.log' -newermt '2026-09-14 09:20' 2>/dev/null | head -10

echo
echo "########## C. nvme SMART 健康 ##########"
sudo smartctl -H -A /dev/nvme0 2>&1 | grep -aiE 'result|Critical|Temperature|Percentage|Available Spare|Media Errors|Unsafe|Power Cycles|Power On Hours|warning' | head -20
echo "--- nvme 错误日志 ---"
sudo smartctl -l error /dev/nvme0 2>&1 | head -15

echo
echo "########## D. amdgpu（0c:00）与内核 PCIe 状态 ##########"
sudo lspci -nn 2>/dev/null | grep -iE 'vga|display|processing|huawei|19e5'
echo "--- amdgpu 相关 dmesg ---"
sudo dmesg -T 2>/dev/null | grep -ai 'amdgpu' | tail -12

echo
echo "########## E. 本周期/上周期 NPU 进程崩溃统计 ##########"
echo "coredump 目录: $(sudo du -sh /var/lib/systemd/coredump 2>/dev/null | awk '{print $1}')  /  根分区剩余: $(df -h / | awk 'NR==2{print $4}')"
echo "--- 各服务崩溃次数（本周期）---"
sudo journalctl -b --no-pager 2>&1 | grep -aoE 'Process [0-9]+ \([a-z_0-9-]+\) of user' | sed 's/.*(\(.*\))/\1/' | sort | uniq -c | sort -rn | head -10
echo "--- 历史 coredump 文件按程序统计 ---"
sudo ls /var/lib/systemd/coredump/ 2>/dev/null | sed 's/^core\.//; s/\.[0-9].*//' | sort | uniq -c | sort -rn | head -10
