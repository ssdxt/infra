#!/bin/bash
IMG=swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/ascendai/npu-exporter:v26.1.0-openeuler24.03-linuxarm64
OFFICIAL_DEV="--device=/dev/davinci0 --device=/dev/davinci1 --device=/dev/davinci_manager --device=/dev/devmm_svm --device=/dev/hisi_hdc"
OFFICIAL_MNT="-v /usr/local/dcmi:/usr/local/dcmi -v /usr/local/bin/npu-smi:/usr/local/bin/npu-smi -v /usr/local/Ascend/driver/lib64/:/usr/local/Ascend/driver/lib64/ -v /usr/local/Ascend/driver/version.info:/usr/local/Ascend/driver/version.info -v /etc/ascend_install.info:/etc/ascend_install.info -v /usr/local/sbin/npu-smi:/usr/local/sbin/npu-smi:ro"
FULL_MNT="-v /usr/local/Ascend/driver:/usr/local/Ascend/driver -v /usr/local/dcmi:/usr/local/dcmi -v /usr/local/sbin/npu-smi:/usr/local/sbin/npu-smi:ro"
CMD='export LD_LIBRARY_PATH=/usr/local/Ascend/driver/lib64/driver:/usr/local/Ascend/driver/lib64/common:/usr/local/Ascend/driver/lib64:/usr/local/dcmi; /usr/local/sbin/npu-smi info 2>&1 | sed -n "1,10p"'

t() { local n="$1"; shift; echo "===== $n ====="; docker run --rm --entrypoint /bin/bash "$@" $IMG -c "$CMD" 2>&1 | sed 's/^/  /'; echo; }

t "1 OFFICIAL 300I DUO + shm-size=1g"     --shm-size=1g $OFFICIAL_DEV $OFFICIAL_MNT
t "2 OFFICIAL without shm-size"                                        $OFFICIAL_DEV $OFFICIAL_MNT
t "3 OFFICIAL + host /dev/shm"            --shm-size=1g $OFFICIAL_DEV $OFFICIAL_MNT -v /dev/shm:/dev/shm
t "4 privileged + host /dev/shm"          --privileged $FULL_MNT -v /dev/shm:/dev/shm
t "5 privileged + shm-size=8g"            --privileged --shm-size=8g $FULL_MNT
t "6 OFFICIAL + ipc=host"                 --shm-size=1g --ipc=host $OFFICIAL_DEV $OFFICIAL_MNT
t "7 OFFICIAL + uts=host"                 --shm-size=1g --uts=host $OFFICIAL_DEV $OFFICIAL_MNT
t "8 OFFICIAL + cap SYS_ADMIN + SYS_RAWIO" --shm-size=1g --cap-add=SYS_ADMIN --cap-add=SYS_RAWIO $OFFICIAL_DEV $OFFICIAL_MNT

echo "===== 9 host /dev/shm size and mount ==="
df -h /dev/shm
mount | grep -E "shm|devmm"

echo
echo "===== 10 does the driver module expose anything the container may lack? ====="
ls -la /sys/module/ | grep -iE "drv_|ascend|devmm|hisi" | head
echo "--- /proc/driver ---"
ls -la /proc/driver/ 2>&1 | head
echo "--- /dev/mqueue /dev/pts in container vs host ---"
docker run --rm --entrypoint /bin/bash --privileged $IMG -c 'ls /dev/ | tr "\n" " "' 2>&1
echo
echo "host /dev:"; ls /dev/ | tr '\n' ' '

echo
echo "===== 11 /etc/davinci or similar host config ====="
ls -la /etc/ | grep -iE "ascend|davinci|hdc|slog|dmp"
ls -la /etc/slog.conf /etc/hdcBasic.cfg /etc/sys_version.conf 2>&1
