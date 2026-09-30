#!/bin/bash
# READ-ONLY log search
echo "########## 0. time reference ##########"
date
echo "--- uptime ---"
cat /proc/uptime
echo "--- /deploy timestamps ---"
ls -la --time-style=full-iso /deploy/ 2>&1 | head -12

echo
echo "########## 1. all .log files under /deploy (sorted by mtime) ##########"
find /deploy -name "*.log" -type f 2>/dev/null -printf "%TY-%Tm-%Td %TH:%TM  %10s  %p\n" | sort -r | head -40

echo
echo "########## 2. glm-4 / mindie related logs anywhere ##########"
find / -xdev \( -name "glm-4.log" -o -name "glm*.log" -o -name "mindservice.log" -o -name "mindie*.log" -o -name "plog-*.log" \) 2>/dev/null | head -30

echo
echo "########## 3. logs modified on 2026-09-14 (yesterday) ##########"
echo "--- under /deploy ---"
find /deploy -type f -newermt "2026-09-13 00:00" ! -newermt "2026-09-15 00:00" 2>/dev/null -printf "%TY-%Tm-%Td %TH:%TM  %10s  %p\n" | sort | head -40
echo "--- under /root ---"
find /root -maxdepth 4 -type f -newermt "2026-09-13 00:00" ! -newermt "2026-09-15 00:00" 2>/dev/null -printf "%TY-%Tm-%Td %TH:%TM  %10s  %p\n" | sort | head -20

echo
echo "########## 4. /deploy/cc/logs ##########"
ls -la --time-style=full-iso /deploy/cc/logs/ 2>&1 | head -20

echo
echo "########## 5. running container glm-4-9b-chat: log files inside ##########"
docker exec glm-4-9b-chat bash -c '
echo "--- cwd ---"; pwd
echo "--- / listing (logs) ---"; ls -la / 2>/dev/null | grep -iE "log"
echo "--- find logs ---"
find / -xdev -name "*.log" -newermt "-2 days" 2>/dev/null | head -20
echo "--- /glm-4.log ---"
ls -la /glm-4.log 2>/dev/null && tail -30 /glm-4.log 2>/dev/null
' 2>&1 | head -50

echo
echo "########## 6. docker logs of glm-4-9b-chat ##########"
docker logs --tail 40 glm-4-9b-chat 2>&1 | head -45

echo
echo "########## 7. /deploy/models/docker_run contents ##########"
ls -laR /deploy/models/docker_run/ 2>&1 | head -30
