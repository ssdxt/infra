#!/bin/bash
echo "=== round 1 (20s) ==="
sleep 20
docker exec oceanbase-ce ss -lnt 2>&1 | head -12
echo "--- container log tail ---"
docker logs --tail 20 oceanbase-ce 2>&1 | tail -20

echo
echo "=== round 2 (40s) ==="
sleep 20
docker exec oceanbase-ce ss -lnt 2>&1 | head -12

echo
echo "=== round 3 (60s) ==="
sleep 20
docker exec oceanbase-ce ss -lnt 2>&1 | head -12

echo
echo "=== round 4 (80s) ==="
sleep 20
docker exec oceanbase-ce ss -lnt 2>&1 | head -12

echo
echo "=== round 5 (100s) ==="
sleep 20
docker exec oceanbase-ce ss -lnt 2>&1 | head -12

echo
echo "=== round 6 (120s) ==="
sleep 20
docker exec oceanbase-ce ss -lnt 2>&1 | head -12

echo
echo "=== full container log ==="
docker logs --tail 80 oceanbase-ce 2>&1 | tail -80

echo
echo "=== process list ==="
docker exec oceanbase-ce ps -ef 2>&1 | head -15

echo
echo "=== /root/ob ==="
docker exec oceanbase-ce ls -la /root/ob 2>&1 | head -12

echo
echo "=== .obd/repository/oceanbase-ce ==="
docker exec oceanbase-ce ls -la /root/.obd/repository/oceanbase-ce/ 2>&1

echo
echo "=== obclient show databases ==="
docker exec oceanbase-ce obclient -h127.1 -P2881 -uroot@test -p12345 -e "show databases;" 2>&1 | head -20

echo
echo "=== obclient sys tenant ==="
docker exec oceanbase-ce obclient -h127.1 -P2881 -uroot -p12345 -e "show databases;" 2>&1 | head -20

echo
echo "=== host tcp 2881 ==="
timeout 6 bash -c 'cat < /dev/null > /dev/tcp/127.0.0.1/2881' 2>/dev/null && echo "2881 OPEN" || echo "2881 CLOSED"

echo
echo "=== docker ps ==="
docker ps --filter name=oceanbase-ce --format '  {{.Names}} | {{.Status}}'
