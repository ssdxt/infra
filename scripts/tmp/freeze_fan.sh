#!/bin/bash
echo "########## A. autofanctrl.service 内容与状态 ##########"
cat /etc/systemd/system/autofanctrl.service 2>&1
echo "--- 状态 ---"
systemctl status autofanctrl --no-pager 2>&1 | head -15
echo "--- 是否 enable ---"
systemctl is-enabled autofanctrl 2>&1
echo "--- 日志（本次启动）---"
sudo journalctl -u autofanctrl -b --no-pager 2>&1 | tail -20

echo
echo "########## B. 它调用的脚本/程序 ##########"
for f in $(grep -aoE '/(usr|opt|root|etc)/[A-Za-z0-9_./-]+' /etc/systemd/system/autofanctrl.service 2>/dev/null | sort -u); do
  echo "--- $f ---"; ls -la "$f" 2>&1; [ -f "$f" ] && sudo head -60 "$f"
done

echo
echo "########## C. 全盘找风扇控制相关脚本 ##########"
sudo find /usr/local/bin /usr/local/sbin /opt /root /etc -maxdepth 3 -iname '*fan*' 2>/dev/null | head -20

echo
echo "########## D. 当前温度与风扇（全部传感器）##########"
sensors 2>&1 | head -40
echo "--- PWM 值 ---"
for p in /sys/class/hwmon/hwmon*/pwm*; do [ -e "$p" ] && echo "$p = $(cat $p 2>/dev/null)"; done | head -20
for f in /sys/class/hwmon/hwmon*/fan*_input; do [ -e "$f" ] && echo "$f = $(cat $f 2>/dev/null)"; done | head -20

echo
echo "########## E. CPU 温度相关 thermal zone ##########"
for z in /sys/class/thermal/thermal_zone*; do
  [ -e "$z/type" ] && echo "$(basename $z) $(cat $z/type 2>/dev/null): $(cat $z/temp 2>/dev/null)"
done
