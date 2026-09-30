#!/bin/bash
IMG=swr.cn-south-1.myhuaweicloud.com/ascendhub/mis-tei:7.3.0-300I-Duo-aarch64
OPT="--security-opt systempaths=unconfined"

echo "########## 1. 镜像里的 HwHiAiUser 是谁 ##########"
sudo docker run --rm $OPT --entrypoint bash "$IMG" -c '
id
echo "--- start.sh 权限 ---"
ls -l /home/HwHiAiUser/start.sh
echo "--- /home/HwHiAiUser 归属 ---"
ls -ld /home/HwHiAiUser
' 2>&1 | head -12

echo
echo "########## 2. 宿主上的 HwHiAiUser ##########"
id HwHiAiUser 2>&1
echo "--- /dev/davinci* 归属 ---"
ls -ln /dev/davinci0 /dev/davinci1 /dev/davinci_manager /dev/devmm_svm /dev/hisi_hdc

echo
echo "########## 3. 默认用户跑你的命令（不带 --user root）→ 看退出原因 ##########"
sudo docker rm -f bge-m3-npu 2>/dev/null >/dev/null
sudo docker run -itd --name bge-m3-npu -p 8000:8000 $OPT \
  --device=/dev/davinci0 --device=/dev/davinci1 \
  --device=/dev/davinci_manager --device=/dev/devmm_svm --device=/dev/hisi_hdc \
  --shm-size=32g \
  -v /usr/local/Ascend/driver:/usr/local/Ascend/driver \
  -v /usr/local/dcmi:/usr/local/dcmi \
  -v /usr/local/bin/npu-smi:/usr/local/bin/npu-smi \
  -v /deploy/models/test/bge-m3:/home/HwHiAiUser/model \
  "$IMG" /bin/bash >/dev/null 2>&1
sleep 5
echo "状态: $(sudo docker ps -a --filter name=^bge-m3-npu$ --format '{{.Status}}')"
echo "--- 容器输出 ---"
sudo docker logs bge-m3-npu 2>&1 | tail -8

echo
echo "########## 4. 加 --user root 再跑 ##########"
sudo docker rm -f bge-m3-npu 2>/dev/null >/dev/null
sudo docker run -itd --name bge-m3-npu -p 8000:8000 $OPT --user root \
  --device=/dev/davinci0 --device=/dev/davinci1 \
  --device=/dev/davinci_manager --device=/dev/devmm_svm --device=/dev/hisi_hdc \
  --shm-size=32g \
  -v /usr/local/Ascend/driver:/usr/local/Ascend/driver \
  -v /usr/local/dcmi:/usr/local/dcmi \
  -v /usr/local/bin/npu-smi:/usr/local/bin/npu-smi \
  -v /deploy/models/test/bge-m3:/home/HwHiAiUser/model \
  "$IMG" /bin/bash >/dev/null 2>&1
sleep 5
echo "状态: $(sudo docker ps -a --filter name=^bge-m3-npu$ --format '{{.Status}}')"
echo "--- 容器输出 ---"
sudo docker logs bge-m3-npu 2>&1 | tail -8
echo "--- 进容器 ---"
sudo docker exec bge-m3-npu bash -c '
echo "whoami: $(whoami)"
echo "NPU: $(ls /dev/davinci* 2>&1 | tr "\n" " ")"
echo "npu-smi:"; npu-smi info 2>&1 | sed -n "4,10p"
echo "模型:"; ls /home/HwHiAiUser/model/ | head -5
' 2>&1 | head -20

echo
echo "########## 5. 清理 ##########"
sudo docker rm -f bge-m3-npu 2>&1 | tail -1
