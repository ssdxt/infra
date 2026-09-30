#!/bin/bash
IMG_NPU=swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/ascendai/npu-exporter:v26.1.0-openeuler24.03-linuxarm64

echo "############ A) /run_for_310P_1usoc.sh 全文（310P 专用启动脚本）############"
docker run --rm --entrypoint /bin/bash $IMG_NPU -c 'cat /run_for_310P_1usoc.sh' 2>&1

echo
echo "############ B) exporter 二进制的参数 ############"
docker run --rm --entrypoint /bin/bash $IMG_NPU -c '/usr/local/bin/npu-exporter --help 2>&1 | head -60' 2>&1

echo
echo "############ C) 配置文件 ############"
docker run --rm --entrypoint /bin/bash $IMG_NPU -c '
  echo "===== metricConfiguration.json ====="
  head -60 /user/mind-cluster/npu-exporter-config/metricConfiguration.json
  echo
  echo "===== pluginConfiguration.json ====="
  head -60 /user/mind-cluster/npu-exporter-config/pluginConfiguration.json
  echo
  echo "===== /user 目录结构 ====="
  ls -laR /user 2>&1 | head -30
' 2>&1

echo
echo "############ D) 宿主侧 npu-smi 与 driver 库（容器要靠 bind mount 拿到）############"
ls /usr/local/Ascend/driver/lib64/driver/ 2>&1 | head -8
ls /usr/local/Ascend/driver/lib64/common/ 2>&1 | head -8
echo "--- dcmi 库在哪（LD_LIBRARY_PATH 里提到 /usr/local/dcmi）---"
ls -la /usr/local/dcmi 2>&1
find /usr/local/Ascend/driver -name "libdcmi*" 2>/dev/null | head
echo "--- driver/tools ---"
ls /usr/local/Ascend/driver/tools/ 2>&1 | head
echo "--- npu-smi ---"
command -v npu-smi; ls -l /usr/local/sbin/npu-smi /usr/local/bin/npu-smi 2>&1
echo "--- add-ons ---"
ls -la /usr/local/Ascend/add-ons/ 2>&1 | head
