#!/bin/bash
IMG=swr.cn-south-1.myhuaweicloud.com/ascendhub/mindie:1.0.0-300I-Duo-py311-openeuler24.03-lts
SVC=/usr/local/Ascend/mindie/latest/mindie-service

echo "===== 1. new container glm-4-9b-chat log ====="
sudo docker exec glm-4-9b-chat bash -c 'ls -la /glm-4.log; echo "--- content ---"; cat /glm-4.log' 2>&1 | tail -40

echo
echo "===== 2. stock image conf keys ====="
sudo docker run --rm --privileged --runtime runc --entrypoint bash "$IMG" -c "
grep -n 'TLSEnabled\|npuDeviceIds\|worldSize\|httpsEnabled\|modelName\|maxInputTokenLen' $SVC/conf/config.json
echo '--- machine_config ---'; ls -la $SVC/conf/machine_config/
echo '--- model_config ---'; ls -la $SVC/conf/model_config/
echo '--- bin ---'; ls -la $SVC/bin/
"

echo
echo "===== 3. app model config ====="
sed -n '80,120p' /deploy/chat_doc_0918/configs/model_config.py

echo
echo "===== 4. host paths ====="
ls -la /deploy/models/glm-4-9b-chat/ | head -30
echo "--- conf ---"
ls -la /deploy/models/glm-4-9b-chat/conf/
