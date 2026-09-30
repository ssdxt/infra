#!/bin/bash
echo "=== 1 host memory ==="
free -g
echo
echo "=== 2 boot/env.sh（deploy 需要的变量）==="
docker exec oceanbase-ce cat /root/boot/env.sh 2>&1
echo
echo "=== 3 current cluster record ==="
ls -la /deploy/infra/oceanbase/obd/cluster/ 2>&1
ls -la /deploy/infra/oceanbase/obd/cluster/obcluster/ 2>&1
cat /deploy/infra/oceanbase/obd/cluster/obcluster/.data 2>&1

echo
echo "=== 4 remove stale cluster record (force fresh deploy) ==="
rm -rf /deploy/infra/oceanbase/obd/cluster/obcluster
rm -rf /deploy/infra/oceanbase/ob/*
ls -la /deploy/infra/oceanbase/obd/cluster/ 2>&1
ls -la /deploy/infra/oceanbase/ob/ 2>&1

echo
echo "=== 5 recreate container ==="
docker rm -f oceanbase-ce 2>&1
bash /deploy/infra/oceanbase/docker-run.sh 2>&1
sleep 30
docker ps --filter name=oceanbase-ce --format '  {{.Names}} | {{.Status}}'

echo
echo "=== 6 log after 60s ==="
sleep 30
docker logs --tail 40 oceanbase-ce 2>&1

echo
echo "=== 7 log after 150s ==="
sleep 90
docker logs --tail 40 oceanbase-ce 2>&1

echo
echo "=== 8 log after 240s ==="
sleep 90
docker logs --tail 50 oceanbase-ce 2>&1

echo
echo "=== 9 obclient test ==="
docker exec oceanbase-ce obclient -h127.1 -P2881 -uroot@test -p12345 -e "show databases;" 2>&1 | head -20

echo
echo "=== 10 internal state ==="
docker exec oceanbase-ce ps -ef 2>&1 | head -12
docker exec oceanbase-ce ss -lnt 2>&1 | head -12

echo
echo "=== 11 host tcp ==="
timeout 6 bash -c 'cat < /dev/null > /dev/tcp/127.0.0.1/2881' 2>/dev/null && echo "2881 OPEN" || echo "2881 CLOSED"
