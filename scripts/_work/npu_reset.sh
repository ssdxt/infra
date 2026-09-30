#!/bin/bash
IMG=swr.cn-south-1.myhuaweicloud.com/ascendhub/mindie:1.0.0-300I-Duo-py311-openeuler24.03-lts

echo "########## 1. 清掉 embed 僵死进程 ##########"
sudo docker stop embed 2>&1 | tail -1
sudo docker rm -f embed 2>&1 | tail -1
sudo pkill -9 -f python-text-emb 2>/dev/null
sleep 3
sudo npu-smi info 2>&1 | sed -n '/Process id/,$p'

echo
echo "########## 2. 复位两颗芯片 ##########"
sudo npu-smi set -t reset -i 24 -c 0 2>&1
sleep 8
sudo npu-smi set -t reset -i 24 -c 1 2>&1
sleep 15

echo
echo "########## 3. 复位后状态 ##########"
sudo npu-smi info 2>&1

echo
echo "########## 4. 复位后再测最小算子 ##########"
for d in 0 1; do
  echo "=========== device $d ==========="
  sudo docker run --rm --privileged --runtime runc --entrypoint bash \
    -v /usr/local/Ascend/driver:/usr/local/Ascend/driver:ro \
    -v /dev/davinci0:/dev/davinci0 -v /dev/davinci1:/dev/davinci1 \
    -v /dev/davinci_manager:/dev/davinci_manager \
    -v /dev/devmm_svm:/dev/devmm_svm -v /dev/hisi_hdc:/dev/hisi_hdc \
    -v /tmp/t.py:/tmp/t.py:ro \
    -e ASCEND_GLOBAL_LOG_LEVEL=3 \
    "$IMG" -c "python3 /tmp/t.py $d" 2>&1 | grep -E ">>>|aicore|errorStr|coreId|retCode|507015|MTE" | head -8
  echo
done
