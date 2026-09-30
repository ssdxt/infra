#!/bin/bash
echo "########## 1. 其他落盘日志源 ##########"
for f in /var/log/messages /var/log/syslog /var/log/kern.log /var/log/boot.log /var/log/dmesg; do
  if [ -e "$f" ]; then echo "[有] $f  ($(ls -l $f | awk '{print $5" bytes, "$6" "$7" "$8}'))"; else echo "[无] $f"; fi
done
echo "--- rsyslog / syslog-ng 状态 ---"
systemctl is-active rsyslog syslog-ng 2>&1 | head -3
echo "--- /var/log 最近修改的 20 个文件 ---"
sudo find /var/log -maxdepth 2 -type f -mmin -600 -printf '%TY-%Tm-%Td %TH:%TM  %10s  %p\n' 2>/dev/null | sort -r | head -20

echo
echo "########## 2. kdump / crash 配置 ##########"
echo "kdump 服务: $(systemctl is-enabled kdump 2>&1) / $(systemctl is-active kdump 2>&1)"
echo "kdump 内存: $(grep -E 'crashkernel' /proc/cmdline 2>/dev/null || echo 'cmdline 无 crashkernel')"
ls -ld /var/crash 2>&1; sudo ls -la /var/crash 2>/dev/null | head -10
ls -ld /var/lib/systemd/pstore /sys/fs/pstore 2>&1
sudo ls -la /sys/fs/pstore 2>/dev/null | head

echo
echo "########## 3. 硬件信息 ##########"
sudo dmidecode -t system -t bios -t memory 2>/dev/null | grep -E 'Manufacturer|Product Name|Serial Number|Version|Release Date|Size:|Locator:|Speed|Part Number|Rank' | head -40

echo
echo "########## 4. 温度 / 风扇 / 电压传感器（sensors）##########"
command -v sensors >/dev/null && sensors 2>&1 | head -60 || echo "无 lm-sensors"
echo "--- thermal zones ---"
for z in /sys/class/thermal/thermal_zone*; do
  [ -e "$z/type" ] && echo "$(cat $z/type): $(awk '{printf "%.1f C", $1/1000}' $z/temp 2>/dev/null)"
done 2>/dev/null | head -20

echo
echo "########## 5. 磁盘 SMART ##########"
lsblk -o NAME,SIZE,TYPE,MOUNTPOINT 2>&1 | head -20
command -v smartctl >/dev/null && echo "smartctl 可用" || echo "无 smartctl"
