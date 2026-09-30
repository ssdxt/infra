#!/bin/bash
IMG=swr.cn-south-1.myhuaweicloud.com/ascendhub/mis-tei:7.3.0-300I-Duo-aarch64
OPT="--security-opt systempaths=unconfined"

echo "########## 1. cut 行为确认（start.sh 里用它解析参数）##########"
sudo docker run --rm $OPT --entrypoint bash "$IMG" -c '
echo -n "  /deploy/models/bge-m3 -> ["; echo "/deploy/models/bge-m3" | cut -d "=" -f2; echo -n "]"
echo -n "  model=/deploy/models/bge-m3 -> ["; echo "model=/deploy/models/bge-m3" | cut -d "=" -f2; echo -n "]"
' 2>&1 | grep -v "^$"

echo
echo "########## 2. 复现你的命令（加上绕过 acpi 的参数），看真实退出原因 ##########"
sudo docker rm -f bge-m3-npu 2>/dev/null >/dev/null
sudo docker run -itd --name bge-m3-npu -p 8000:8000 \
  $OPT \
  --device=/dev/davinci0 --device=/dev/davinci1 \
  --device=/dev/davinci_manager --device=/dev/devmm_svm --device=/dev/hisi_hdc \
  --shm-size=32g \
  -v /usr/local/Ascend/driver:/usr/local/Ascend/driver \
  -v /usr/local/dcmi:/usr/local/dcmi \
  -v /usr/local/bin/npu-smi:/usr/local/bin/npu-smi \
  -v /deploy/models/test/bge-m3:/home/HwHiAiUser/model \
  "$IMG" /bin/bash 2>&1 | tail -2
sleep 5
echo "状态: $(sudo docker ps -a --filter name=^bge-m3-npu$ --format '{{.Status}}')"
echo "--- 容器输出 ---"
sudo docker logs bge-m3-npu 2>&1 | tail -10

echo
echo "########## 3. 正确启动方式：--entrypoint /bin/bash ##########"
sudo docker rm -f bge-m3-npu 2>/dev/null >/dev/null
sudo docker run -itd --name bge-m3-npu -p 8000:8000 \
  $OPT \
  --device=/dev/davinci0 --device=/dev/davinci1 \
  --device=/dev/davinci_manager --device=/dev/devmm_svm --device=/dev/hisi_hdc \
  --shm-size=32g \
  -v /usr/local/Ascend/driver:/usr/local/Ascend/driver \
  -v /usr/local/dcmi:/usr/local/dcmi \
  -v /usr/local/bin/npu-smi:/usr/local/bin/npu-smi \
  -v /deploy/models/test/bge-m3:/home/HwHiAiUser/model \
  --entrypoint /bin/bash \
  "$IMG" 2>&1 | tail -2
sleep 5
echo "状态: $(sudo docker ps -a --filter name=^bge-m3-npu$ --format '{{.Status}}')"
echo "--- 进容器验证 ---"
sudo docker exec bge-m3-npu bash -c '
echo "whoami: $(whoami)"
echo "NPU: $(ls /dev/davinci* 2>&1 | tr "\n" " ")"
echo "模型目录:"; ls /home/HwHiAiUser/model/ | head -6
' 2>&1 | head -15

echo
echo "########## 4. 清理 ##########"
sudo docker rm -f bge-m3-npu 2>&1 | tail -1
