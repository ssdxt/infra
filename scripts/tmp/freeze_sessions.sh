#!/bin/bash
echo "########## 每个启动周期，syslog 的最后一条记录 + 是否有序关机 ##########"
for f in /var/log/syslog.3.gz /var/log/syslog.2.gz /var/log/syslog.1.gz /var/log/syslog; do
  echo "==================== $f ===================="
  if [[ "$f" == *.gz ]]; then CAT="zcat"; else CAT="cat"; fi
  echo "首行: $($CAT $f 2>/dev/null | head -1 | cut -c1-120)"
  echo "末行: $($CAT $f 2>/dev/null | tail -1 | cut -c1-120)"
  echo "--- 该文件内的每次关机/启动事件（systemd 关机序列）---"
  $CAT $f 2>/dev/null | grep -aE 'Reached target (Shutdown|Reboot|Power-Off|Halt)|Shutting down|Stopping .*\.\.\.$|Unmounting|systemd-shutdown|Powering off|Rebooting|Startup finished in' | grep -aE 'Reached target|systemd-shutdown|Startup finished' | tail -12
  echo "--- 该文件末尾最后 12 行 ---"
  $CAT $f 2>/dev/null | tail -12 | cut -c1-150
  echo
done
