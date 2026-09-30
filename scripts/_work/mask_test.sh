#!/bin/bash
IMG=swr.cn-south-1.myhuaweicloud.com/ascendhub/mis-tei:7.3.0-300I-Duo-aarch64

echo "########## 1. 环境检查 ##########"
echo "--- /usr/local/dcmi 存在吗 ---"
ls -la /usr/local/dcmi 2>&1 | head -5
echo "--- /deploy/models/test/bge-m3 ---"
ls -la /deploy/models/test/bge-m3 2>&1 | head -5
echo "--- 内核 ---"
uname -r
echo "--- docker 默认 maskedPaths 里 /proc/acpi 的写法 ---"
sudo docker inspect $(sudo docker ps -q | head -1) --format '{{range .HostConfig.MaskedPaths}}{{.}}
{{end}}' 2>/dev/null | grep -n "proc/acpi\|proc/asound\|proc/kcore" | head

echo
echo "########## 2. 清理刚才失败的容器 ##########"
sudo docker rm -f bge-m3-npu 2>&1 | tail -1

echo
echo "########## 3. 方案A：--security-opt systempaths=unconfined（只解除 masked/readonly paths）##########"
sudo docker rm -f t-a 2>/dev/null >/dev/null
sudo docker run -d --name t-a \
  --security-opt systempaths=unconfined \
  --device=/dev/davinci0 --device=/dev/davinci1 \
  --device=/dev/davinci_manager --device=/dev/devmm_svm --device=/dev/hisi_hdc \
  --shm-size=32g \
  -v /usr/local/Ascend/driver:/usr/local/Ascend/driver \
  -v /usr/local/dcmi:/usr/local/dcmi \
  -v /usr/local/bin/npu-smi:/usr/local/bin/npu-smi \
  -v /deploy/models/test/bge-m3:/home/HwHiAiUser/model \
  "$IMG" /bin/bash 2>&1 | tail -3
sleep 4
echo "结果: $(sudo docker ps -a --filter name=^t-a$ --format '{{.Status}}')"

echo
echo "########## 4. 方案B：--privileged（对照）##########"
sudo docker rm -f t-b 2>/dev/null >/dev/null
sudo docker run -d --name t-b \
  --privileged \
  --device=/dev/davinci0 --device=/dev/davinci1 \
  --device=/dev/davinci_manager --device=/dev/devmm_svm --device=/dev/hisi_hdc \
  --shm-size=32g \
  -v /usr/local/Ascend/driver:/usr/local/Ascend/driver \
  -v /usr/local/dcmi:/usr/local/dcmi \
  -v /usr/local/bin/npu-smi:/usr/local/bin/npu-smi \
  -v /deploy/models/test/bge-m3:/home/HwHiAiUser/model \
  "$IMG" /bin/bash 2>&1 | tail -3
sleep 4
echo "结果: $(sudo docker ps -a --filter name=^t-b$ --format '{{.Status}}')"

echo
echo "########## 5. 方案A 容器里能不能看到 NPU ##########"
sudo docker exec t-a bash -c 'ls -l /dev/davinci* /dev/davinci_manager 2>&1; echo "--- npu-smi ---"; npu-smi info 2>&1 | head -12' 2>&1 | head -22

echo
echo "########## 6. 清理测试容器 ##########"
sudo docker rm -f t-a t-b 2>&1 | tail -2
