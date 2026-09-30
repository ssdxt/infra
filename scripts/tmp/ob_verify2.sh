#!/bin/bash
echo "--- tcp probe 2881 from host ---"
timeout 5 bash -c 'exec 3<>/dev/tcp/127.0.0.1/2881 && echo "connect OK" || echo "connect FAIL"'
echo
echo "--- host mysql/obclient? ---"
command -v mysql obclient 2>&1
echo
echo "--- look for client inside container ---"
sudo docker exec oceanbase-ce bash -c 'ls /root/ob/bin 2>/dev/null | head -20; command -v obclient mysql 2>&1'
echo
echo "--- observer process ---"
sudo docker exec oceanbase-ce bash -c 'ps -eo pid,pcpu,pmem,etime,comm | grep -E "observer|obshell" | grep -v grep'
echo
echo "--- container status now ---"
sudo docker ps --filter name=oceanbase-ce --format '{{.Names}} | {{.Status}} | {{.RunningFor}}'
echo
echo "--- warnings only in last 200 log lines (errors?) ---"
sudo docker logs --tail 200 oceanbase-ce 2>&1 | grep -iE 'error|fail' | tail -10
echo "(no output above = no error/fail lines)"
