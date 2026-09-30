#!/bin/bash
S=/data1/apps/wxq-plant01-monitor/scripts/watchdog-heartbeat.sh
sed -i 's|http://prometheus-alert:8080|http://localhost:8280|g' $S
echo -n "修正后通道: "; grep -o 'HOOK=.*' $S | head -1
echo ""
echo "--- 故障路径演练（TEST=1，发测试钉钉）"
TEST=1 bash $S
echo ""
echo "--- cron 完整性"
ls -la /etc/cron.d/watchdog-heartbeat | awk '{print "  "$1, $NF}'
crontab -l 2>/dev/null | grep -c watchdog | sed 's/^/  root crontab 相关行(应为0,用cron.d)=/'