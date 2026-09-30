#!/bin/bash
echo "=== 1: full find for dmp_daemon / slogd ==="
find / -xdev \( -name "dmp_daemon*" -o -name "slogd*" \) 2>/dev/null | head -20
echo "(end find)"

echo
echo "=== 2: ascend related systemd units ==="
systemctl list-unit-files 2>/dev/null | grep -iE "ascend|davinci|slog|dmp|npu|hdc" || echo "none"
echo "--- running ---"
systemctl list-units --all 2>/dev/null | grep -iE "ascend|davinci|slog|dmp|npu|hdc" || echo "none"

echo
echo "=== 3: host_servers_setup.sh (read only, first 60 lines) ==="
head -60 /usr/local/Ascend/host_servers_setup.sh 2>&1
echo "..."
echo "--- does it mention dmp_daemon / slogd ? ---"
grep -n "dmp_daemon\|slogd" /usr/local/Ascend/host_servers_setup.sh /usr/local/Ascend/host_sys_init.sh /usr/local/Ascend/host_services_setup.sh 2>/dev/null

echo
echo "=== 4: driver script dir ==="
ls -la /usr/local/Ascend/driver/script/ 2>&1
echo "--- driver/device dir ---"
ls -la /usr/local/Ascend/driver/device/ 2>&1 | head

echo
echo "=== 5: /etc/ascend_install.info ==="
cat /etc/ascend_install.info 2>&1

echo
echo "=== 6: container side - devices and libs ==="
docker inspect -f 'runtime={{.HostConfig.Runtime}} priv={{.HostConfig.Privileged}} devices={{.HostConfig.Devices}}' npu-exporter 2>&1
echo "--- /dev inside container ---"
docker exec npu-exporter ls -la /dev/ 2>&1 | grep -iE "davinci|devmm|hisi|dmp|hdc" || echo "no asc devices visible"
echo "--- /proc/devices ---"
docker exec npu-exporter sh -c 'grep -iE "davinci|devmm|hisi" /proc/devices' 2>&1
echo "--- driver libs inside container ---"
docker exec npu-exporter sh -c 'ls /usr/local/Ascend/driver/lib64/driver/ 2>&1 | head -12' 2>&1
docker exec npu-exporter sh -c 'ls /usr/local/dcmi/ 2>&1' 2>&1
echo "--- /var/slogd /var/dmp_daemon inside container ---"
docker exec npu-exporter sh -c 'ls -la /var/slogd /var/dmp_daemon 2>&1' 2>&1

echo
echo "=== 7: host npu-smi still ok? ==="
/usr/local/sbin/npu-smi info 2>&1 | head -12

echo
echo "=== 8: exporter current status and full log ==="
docker ps --filter name=npu-exporter --format '{{.Names}} | {{.Status}}'
echo "--- full container log ---"
docker logs npu-exporter 2>&1 | tail -25
echo "--- exporter file log ---"
tail -25 /var/log/mindx-dl/npu-exporter/npu-exporter.log 2>&1

echo
echo "=== 9: what npu-exporter expects (dry run with -version) ==="
docker run --rm --entrypoint /bin/bash \
  -v /usr/local/Ascend/driver:/usr/local/Ascend/driver \
  -v /usr/local/dcmi:/usr/local/dcmi \
  --privileged \
  swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/ascendai/npu-exporter:v26.1.0-openeuler24.03-linuxarm64 \
  -c 'ls -la /dev/ | grep -iE "davinci|devmm|hisi"; echo "---"; export LD_LIBRARY_PATH=/usr/local/Ascend/driver/lib64/driver:/usr/local/Ascend/driver/lib64/common:/usr/local/Ascend/driver/lib64:/usr/local/dcmi; /usr/local/bin/npu-exporter -version 2>&1 | head -5' 2>&1
