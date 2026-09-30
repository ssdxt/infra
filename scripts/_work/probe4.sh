#!/bin/bash
IMG=swr.cn-south-1.myhuaweicloud.com/ascendhub/mindie:1.0.0-300I-Duo-py311-openeuler24.03-lts

echo "===== host uid map ====="
id kzzk 2>&1
id HwHiAiUser 2>&1
awk -F: '$3>=0 && $3<1100 {print $1" uid="$3" gid="$4" home="$6}' /etc/passwd

echo
echo "===== host device ownership ====="
ls -ln /dev/davinci0 /dev/davinci1 /dev/davinci_manager /dev/devmm_svm /dev/hisi_hdc

echo
echo "===== host driver dir ownership ====="
ls -ld /usr/local/Ascend/driver /usr/local/Ascend/driver/lib64 /usr/local/Ascend/driver/lib64/driver 2>&1
ls -ln /usr/local/Ascend/driver/lib64/driver/ 2>&1 | head -5

echo
echo "===== container uid 1000 ====="
sudo docker run --rm --privileged --runtime runc --entrypoint bash "$IMG" -c '
id 1000 2>&1
echo "--- passwd ---"
cat /etc/passwd
echo "--- key file owners ---"
ls -ln /usr/local/Ascend/mindie/latest/mindie-service/lib/libmindieservice_llm_engine.so 2>&1
find /usr/local/Ascend/mindie -name "libmindieservice_llm_engine.so" -exec ls -ln {} \; 2>/dev/null
echo "--- driver in container ---"
ls -ln /usr/local/Ascend/driver/lib64/driver 2>&1 | head -3
'

echo
echo "===== host /deploy/models ownership ====="
ls -ldn /deploy/models /deploy/models/glm-4-9b-chat /deploy/models/glm-4-9b-chat/conf
ls -ln /deploy/models/glm-4-9b-chat/conf/
