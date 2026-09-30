#!/bin/bash
IMG=swr.cn-south-1.myhuaweicloud.com/ascendhub/mis-tei:7.3.0-300I-Duo-aarch64

echo "########## 1. 镜像的 ENTRYPOINT / CMD / WORKDIR ##########"
sudo docker image inspect "$IMG" --format 'Entrypoint={{json .Config.Entrypoint}}
Cmd={{json .Config.Cmd}}
WorkDir={{.Config.WorkingDir}}
User={{.Config.User}}'

echo
echo "########## 2. 交互式启动测试（加 -it，跟你原来的写法一致）##########"
sudo docker rm -f t-a 2>/dev/null >/dev/null
sudo docker run -itd --name t-a \
  --security-opt systempaths=unconfined \
  --device=/dev/davinci0 --device=/dev/davinci1 \
  --device=/dev/davinci_manager --device=/dev/devmm_svm --device=/dev/hisi_hdc \
  --shm-size=32g \
  -v /usr/local/Ascend/driver:/usr/local/Ascend/driver \
  -v /usr/local/dcmi:/usr/local/dcmi \
  -v /usr/local/bin/npu-smi:/usr/local/bin/npu-smi \
  -v /deploy/models/test/bge-m3:/home/HwHiAiUser/model \
  "$IMG" /bin/bash 2>&1 | tail -2
sleep 5
echo "状态: $(sudo docker ps -a --filter name=^t-a$ --format '{{.Status}}')"

echo
echo "########## 3. 进容器验证 ##########"
sudo docker exec t-a bash -c '
echo "--- whoami ---"; whoami
echo "--- NPU 设备 ---"; ls -l /dev/davinci0 /dev/davinci1 /dev/davinci_manager 2>&1
echo "--- npu-smi ---"; npu-smi info 2>&1 | sed -n "1,12p"
echo "--- 模型目录 ---"; ls /home/HwHiAiUser/model/ | head -8
echo "--- start.sh ---"; ls -l /home/HwHiAiUser/start.sh 2>&1
' 2>&1 | head -40

echo
echo "########## 4. 清理 ##########"
sudo docker rm -f t-a 2>&1 | tail -1
