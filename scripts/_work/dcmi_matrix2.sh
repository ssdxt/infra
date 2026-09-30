#!/bin/bash
IMG=swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/ascendai/npu-exporter:v26.1.0-openeuler24.03-linuxarm64
MNT="-v /usr/local/Ascend/driver:/usr/local/Ascend/driver -v /usr/local/dcmi:/usr/local/dcmi -v /usr/local/sbin/npu-smi:/usr/local/sbin/npu-smi:ro"
DEV="--device=/dev/davinci0 --device=/dev/davinci1 --device=/dev/davinci_manager --device=/dev/devmm_svm --device=/dev/hisi_davinci_intf --device=/dev/hisi_hdc"
CMD='export LD_LIBRARY_PATH=/usr/local/Ascend/driver/lib64/driver:/usr/local/Ascend/driver/lib64/common:/usr/local/Ascend/driver/lib64:/usr/local/dcmi; /usr/local/sbin/npu-smi info 2>&1 | sed -n "1,10p"'

t() { local n="$1"; shift; echo "===== $n ====="; docker run --rm --entrypoint /bin/bash "$@" $IMG -c "$CMD" 2>&1 | sed 's/^/  /'; echo; }

t "A runc + devices + mounts"                 --runtime=runc $DEV $MNT
t "B runc + privileged + mounts"              --runtime=runc --privileged $MNT
t "C ascend + ASCEND_VISIBLE_DEVICES + dev"   -e ASCEND_VISIBLE_DEVICES=0,1 $DEV $MNT
t "D ascend + ASCEND_VISIBLE_DEVICES + priv"  -e ASCEND_VISIBLE_DEVICES=0,1 --privileged $MNT
t "E runc + ASCEND_VISIBLE_DEVICES + dev"     --runtime=runc -e ASCEND_VISIBLE_DEVICES=0,1 $DEV $MNT
t "F ascend + dev only (no mounts)"           $DEV

echo "===== G: what does the ascend hook actually do to mounts? ====="
docker rm -f hooktest 2>/dev/null
docker run -d --name hooktest -e ASCEND_VISIBLE_DEVICES=0,1 $MNT $IMG sleep 300 2>&1 | tail -2
sleep 3
echo "--- container mounts (ascend runtime) ---"
docker inspect -f '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}' hooktest 2>&1 | head -20
echo "--- devices inside ---"
docker exec hooktest ls -la /dev/ 2>&1 | grep -iE "davinci|devmm|hisi" | head
echo "--- ASCEND env inside ---"
docker exec hooktest env 2>&1 | grep -i ascend
docker rm -f hooktest >/dev/null 2>&1

echo
echo "===== H: same but runc ====="
docker rm -f hooktest2 2>/dev/null
docker run -d --name hooktest2 --runtime=runc -e ASCEND_VISIBLE_DEVICES=0,1 $MNT $IMG sleep 300 2>&1 | tail -2
sleep 3
docker inspect -f '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}' hooktest2 2>&1 | head -20
docker exec hooktest2 ls -la /dev/ 2>&1 | grep -iE "davinci|devmm|hisi" | head
docker rm -f hooktest2 >/dev/null 2>&1

echo
echo "===== I: host-side device nodes ====="
ls -la /dev/davinci* /dev/devmm_svm /dev/hisi_hdc /dev/hisi_davinci_intf 2>&1
echo "--- host /proc/devices ---"
grep -iE "davinci|devmm|hisi" /proc/devices

echo
echo "===== J: driver log for the -9005 failure ====="
ls -la /var/log/npu/ 2>&1
find /var/log/npu -name "*.log" -newermt "-30 minutes" 2>/dev/null | head
tail -30 /var/log/npu/slog/device-0/*.log 2>/dev/null | head -30
dmesg -T 2>/dev/null | tail -20
