#!/bin/bash
IMG=swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/ascendai/npu-exporter:v26.1.0-openeuler24.03-linuxarm64

echo "=== 1: ldd libdcmi inside container (missing deps?) ==="
docker exec npu-exporter sh -c 'ldd /usr/local/Ascend/driver/lib64/driver/libdcmi.so 2>&1' 2>&1
echo "--- libdrvdsmi_host.so ---"
docker exec npu-exporter sh -c 'ldd /usr/local/Ascend/driver/lib64/driver/libdrvdsmi_host.so 2>&1' 2>&1

echo
echo "=== 2: host ld.so.conf.d for Ascend ==="
grep -rl Ascend /etc/ld.so.conf.d/ 2>/dev/null
for f in $(grep -rl Ascend /etc/ld.so.conf.d/ 2>/dev/null); do echo "--- $f ---"; cat "$f"; done
echo "--- driver/lib64 subdirs ---"
ls /usr/local/Ascend/driver/lib64/
echo "--- inner ---"
ls /usr/local/Ascend/driver/lib64/inner/ 2>&1 | head
echo "--- ldd libdcmi on HOST ---"
ldd /usr/local/Ascend/driver/lib64/driver/libdcmi.so 2>&1 | grep -i "not found" || echo "  host: no missing deps"

echo
echo "=== 3: kernel modules ==="
lsmod 2>/dev/null | grep -iE "davinci|devmm|hisi|drv" | head -10

echo
echo "=== 4: DECISIVE - run the exporter binary directly on the HOST ==="
docker rm -f tmpx 2>/dev/null
docker create --name tmpx --entrypoint /bin/true $IMG >/dev/null 2>&1
docker cp tmpx:/usr/local/bin/npu-exporter /tmp/npu-exp-host >/dev/null 2>&1
docker rm -f tmpx >/dev/null 2>&1
chmod 755 /tmp/npu-exp-host
ls -la /tmp/npu-exp-host
rm -f /tmp/npuexp-host.log
LD_LIBRARY_PATH=/usr/local/Ascend/driver/lib64/driver:/usr/local/Ascend/driver/lib64/common:/usr/local/Ascend/driver/lib64:/usr/local/dcmi \
  nohup /tmp/npu-exp-host -port=8083 -ip=127.0.0.1 -logFile=/tmp/npuexp-host.log -logLevel=0 -containerMode=docker >/tmp/npuexp-host.stdout 2>&1 &
HPID=$!
echo "  started pid=$HPID, waiting 12s"
sleep 12
echo "--- host-run log ---"
cat /tmp/npuexp-host.log 2>&1 | tail -20
echo "--- host-run stdout ---"
tail -10 /tmp/npuexp-host.stdout 2>&1
echo "--- probe 8083 ---"
curl -s -m 8 -o /tmp/hostnpu.txt -w "  http_code=%{http_code}\n" http://127.0.0.1:8083/metrics
echo "  npu_ lines: $(grep -c '^npu_' /tmp/hostnpu.txt 2>/dev/null)"
grep -E '^npu_chip_info_(name|health_status|temperature)' /tmp/hostnpu.txt 2>/dev/null | head -6
kill $HPID 2>/dev/null
sleep 1
pkill -f npu-exp-host 2>/dev/null
echo "  cleaned up"

echo
echo "=== 5: npu-smi INSIDE the container (mount host binary) ==="
docker run --rm --privileged \
  -v /usr/local/Ascend/driver:/usr/local/Ascend/driver \
  -v /usr/local/dcmi:/usr/local/dcmi \
  -v /usr/local/sbin/npu-smi:/usr/local/sbin/npu-smi:ro \
  --entrypoint /bin/bash $IMG \
  -c 'export LD_LIBRARY_PATH=/usr/local/Ascend/driver/lib64/driver:/usr/local/Ascend/driver/lib64/common:/usr/local/Ascend/driver/lib64:/usr/local/dcmi; /usr/local/sbin/npu-smi info 2>&1 | head -20' 2>&1

echo
echo "=== 6: is there anything in /usr/local/Ascend/driver/lib64/inner the exporter needs? ==="
docker exec npu-exporter sh -c 'ls /usr/local/Ascend/driver/lib64/inner/ 2>&1 | head -10' 2>&1

echo
echo "=== 7: env inside running exporter container ==="
docker exec npu-exporter sh -c 'env | sort | grep -iE "ascend|npu|runtime|visible"' 2>&1
echo "(end)"
