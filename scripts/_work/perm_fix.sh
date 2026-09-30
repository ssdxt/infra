#!/bin/bash
IMG=swr.cn-south-1.myhuaweicloud.com/ascendhub/mis-tei:7.3.0-300I-Duo-aarch64
OPT="--security-opt systempaths=unconfined"
DEV="--device=/dev/davinci0 --device=/dev/davinci1 --device=/dev/davinci_manager --device=/dev/devmm_svm --device=/dev/hisi_hdc"

echo "########## 1. cut 解析行为（决定 <model_id> 怎么传）##########"
sudo docker run --rm $OPT --entrypoint bash "$IMG" -c '
printf "  [/deploy/models/bge-m3] -> basename=["; echo "/deploy/models/bge-m3" | cut -d "=" -f2 | sed "s/\/*$//g" | awk -F/ "{print \$NF}"; printf "]\n"
printf "  [bge-m3]               -> basename=["; echo "bge-m3" | cut -d "=" -f2 | sed "s/\/*$//g" | awk -F/ "{print \$NF}"; printf "]\n"
' 2>&1 | grep -E "basename"

echo
echo "########## 2. 修正版：进 bash 交互容器（应该保持 Up）##########"
sudo docker rm -f bge-m3-npu 2>/dev/null >/dev/null
sudo docker run -itd --name bge-m3-npu -p 8000:8000 $OPT --user root $DEV --shm-size=32g \
  -v /usr/local/Ascend/driver:/usr/local/Ascend/driver \
  -v /usr/local/dcmi:/usr/local/dcmi \
  -v /usr/local/bin/npu-smi:/usr/local/bin/npu-smi \
  -v /deploy/models/test/bge-m3:/home/HwHiAiUser/model \
  --entrypoint /bin/bash \
  "$IMG" 2>&1 | tail -1
sleep 6
echo "状态: $(sudo docker ps -a --filter name=^bge-m3-npu$ --format '{{.Status}}')"
echo "--- 容器内 ---"
sudo docker exec bge-m3-npu bash -c '
echo "whoami       : $(whoami)"
echo "NPU 设备     : $(ls /dev/davinci* 2>&1 | tr "\n" " ")"
echo "npu-smi      :"; npu-smi info 2>&1 | sed -n "4,6p"
echo "模型目录     : $(ls /home/HwHiAiUser/model/ | head -4 | tr "\n" " ")"
echo "start.sh     : $(test -r /home/HwHiAiUser/start.sh && echo 可读 || echo 不可读)"
' 2>&1 | head -18

echo
echo "########## 3. 直接起 TEI 服务（挂载改成 test 目录，参数 3 个）##########"
sudo docker rm -f bge-m3-npu 2>/dev/null >/dev/null
sudo docker run -itd --name bge-m3-npu -p 8000:8000 $OPT --user root $DEV --shm-size=32g \
  -v /usr/local/Ascend/driver:/usr/local/Ascend/driver \
  -v /usr/local/dcmi:/usr/local/dcmi \
  -v /usr/local/bin/npu-smi:/usr/local/bin/npu-smi \
  -v /deploy/models/test:/home/HwHiAiUser/model \
  "$IMG" /deploy/models/test/bge-m3 0.0.0.0 8000 >/dev/null 2>&1
sleep 25
echo "状态: $(sudo docker ps -a --filter name=^bge-m3-npu$ --format '{{.Status}}')"
echo "--- 日志 ---"
sudo docker logs bge-m3-npu 2>&1 | grep -vE "^\s*$" | tail -12

echo
echo "########## 4. 清理 ##########"
sudo docker rm -f bge-m3-npu 2>&1 | tail -1
