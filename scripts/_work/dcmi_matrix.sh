#!/bin/bash
IMG=swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/ascendai/npu-exporter:v26.1.0-openeuler24.03-linuxarm64
DEV="--device=/dev/davinci0 --device=/dev/davinci1 --device=/dev/davinci_manager --device=/dev/devmm_svm --device=/dev/hisi_hdc"
MNT="-v /usr/local/Ascend/driver:/usr/local/Ascend/driver -v /usr/local/dcmi:/usr/local/dcmi -v /usr/local/sbin/npu-smi:/usr/local/sbin/npu-smi:ro"
CMD='export LD_LIBRARY_PATH=/usr/local/Ascend/driver/lib64/driver:/usr/local/Ascend/driver/lib64/common:/usr/local/Ascend/driver/lib64:/usr/local/dcmi; /usr/local/sbin/npu-smi info 2>&1 | sed -n "1,10p"'

probe() {
  local name="$1"; shift
  echo "===== $name ====="
  docker run --rm --entrypoint /bin/bash "$@" $IMG -c "$CMD" 2>&1 | sed 's/^/  /'
  echo
}

echo "### 0: filelist.csv - should dmp_daemon/slogd exist? ###"
grep -n "dmp_daemon\|slogd" /usr/local/Ascend/driver/script/filelist.csv 2>/dev/null | head -10 || echo "  not listed in driver filelist.csv"
echo "--- Ascend-Docker-Runtime contents ---"
find /usr/local/Ascend/Ascend-Docker-Runtime -maxdepth 2 2>/dev/null | head -20
echo "--- host /var/log/npu ---"
ls -la /var/log/npu 2>&1 | head -5

echo
echo "### 1: baseline: privileged + mounts (known FAIL) ###"
probe "1-privileged" --privileged $MNT

echo "### 2: + /etc/ascend_install.info ###"
probe "2-install-info" --privileged $MNT -v /etc/ascend_install.info:/etc/ascend_install.info:ro

echo "### 3: + /var/log/npu -> /usr/slog ###"
probe "3-slog" --privileged $MNT -v /var/log/npu:/usr/slog

echo "### 4: devices only, no privileged, runtime=ascend ###"
probe "4-devices-ascend" --runtime=ascend $DEV $MNT

echo "### 5: privileged + ld.so.conf.d ###"
probe "5-ldconf" --privileged $MNT -v /etc/ld.so.conf.d/ascend_driver_so.conf:/etc/ld.so.conf.d/ascend_driver_so.conf:ro

echo "### 6: privileged + all security opts unconfined ###"
probe "6-unconfined" --privileged --security-opt seccomp=unconfined --security-opt apparmor=unconfined --security-opt label=disable $MNT

echo "### 7: privileged + whole /usr/local/Ascend ###"
probe "7-whole-ascend" --privileged -v /usr/local/Ascend:/usr/local/Ascend -v /usr/local/sbin/npu-smi:/usr/local/sbin/npu-smi:ro -v /usr/local/dcmi:/usr/local/dcmi

echo "### 8: devices + privileged + ipc=host + pid=host ###"
probe "8-ipc-pid" --privileged --ipc=host --pid=host $MNT

echo "### 9: host netns + privileged ###"
probe "9-net-host" --privileged --net=host $MNT

echo "### 10: full house: privileged + everything ###"
probe "10-full" --privileged --ipc=host --pid=host --net=host \
  $MNT -v /etc/ascend_install.info:/etc/ascend_install.info:ro \
  -v /var/log/npu:/usr/slog \
  -v /etc/ld.so.conf.d/ascend_driver_so.conf:/etc/ld.so.conf.d/ascend_driver_so.conf:ro

echo "### 11: device cgroup check inside container ###"
docker run --rm --privileged --entrypoint /bin/bash $MNT $IMG -c 'cat /sys/fs/cgroup/devices/devices.list 2>/dev/null | head -3; echo "---"; cat /proc/self/status | grep -i cap' 2>&1 | head -8

echo
echo "### 12: does the container kernel see the devices in /sys? ###"
docker run --rm --privileged --entrypoint /bin/bash $IMG -c 'ls /sys/class/ 2>/dev/null | grep -i davinci; echo "--- /sys/devices ---"; ls /sys/devices/ 2>/dev/null | grep -i davinci | head; echo "--- host vs container /sys/class/davinci ---"' 2>&1 | head -12
echo "host side:"
ls /sys/class/ 2>/dev/null | grep -i davinci | head
