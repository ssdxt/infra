#!/bin/bash
MON=/deploy/infra/monitor
mkdir -p "$MON" /var/log/mindx-dl/npu-exporter

echo "=== A: file sanity ==="
wc -c "$MON/docker-compose.yml"
md5sum "$MON/docker-compose.yml"
echo "--- non-ascii byte count ---"
LC_ALL=C grep -c '[^ -~]' "$MON/docker-compose.yml"
echo "--- lines 1-45 with cat -A to expose hidden chars ---"
sed -n '1,45p' "$MON/docker-compose.yml" | cat -A | sed -n '1,45p'

echo
echo "=== B: compose config resolution ==="
cd "$MON" || exit 1
/usr/bin/docker-compose config 2>&1 | head -60
echo "config rc=$?"

echo
echo "=== C: up -d ==="
docker rm -f node-exporter npu-exporter 2>/dev/null
/usr/bin/docker-compose up -d 2>&1 | tail -20

echo
echo "=== D: wait 15s ==="
sleep 15
/usr/bin/docker-compose ps 2>&1

echo
echo "=== E: npu-exporter logs ==="
docker logs --tail 40 npu-exporter 2>&1 | tail -40

echo
echo "=== F: node-exporter logs ==="
docker logs --tail 15 node-exporter 2>&1 | tail -15

echo
echo "=== G: probe 8082 ==="
curl -s -m 10 -o /tmp/npu.txt -w "http_code=%{http_code}\n" http://127.0.0.1:8082/metrics
echo -n "npu_ lines="; grep -c '^npu_' /tmp/npu.txt 2>/dev/null
head -5 /tmp/npu.txt 2>/dev/null
grep -E '^npu_chip_info_' /tmp/npu.txt 2>/dev/null | head -10

echo
echo "=== H: probe 11256 healthz ==="
curl -s -m 5 -o /dev/null -w "http_code=%{http_code}\n" http://127.0.0.1:11256/healthz

echo
echo "=== I: probe 9100 ==="
curl -s -m 10 -o /tmp/node.txt -w "http_code=%{http_code}\n" http://127.0.0.1:9100/metrics
echo -n "node_ lines="; grep -c '^node_' /tmp/node.txt 2>/dev/null
grep -E '^node_(uname|load1|memory_MemTotal_bytes)' /tmp/node.txt 2>/dev/null | head -3

echo
echo "=== J: ports ==="
ss -lntp 2>/dev/null | grep -E ':(8082|11256|9100)'

echo
echo "=== K: log file ==="
ls -la /var/log/mindx-dl/npu-exporter/ 2>&1
tail -20 /var/log/mindx-dl/npu-exporter/npu-exporter.log 2>&1

echo
echo "=== L: summary ==="
docker ps -a --filter name=exporter --format '{{.Names}} | {{.Status}} | {{.Ports}}'
