#!/bin/bash
echo "########## 1. 杀掉卡死的 ripgrep ##########"
ps -eo pid,etimes,%cpu,comm | grep -E "^\s*[0-9]+\s+[0-9]+\s+[0-9]+\s+rg$" | head
sudo pkill -9 -x rg 2>/dev/null
sudo pkill -9 -f "ripgrep-universal" 2>/dev/null
sleep 3
echo "--- 剩余 rg ---"
ps -ef | grep "[r]g " | head -3 || echo "已清空"

echo
echo "########## 2. 负载变化 ##########"
uptime

echo
echo "########## 3. 清理 /tmp 残留 ##########"
sudo docker exec bge-m3-npu bash -c '
rm -f /tmp/text-embeddings-inference-server
rm -rf /tmp/tmp????????? 2>/dev/null
ls -la /tmp/ | head -10
' 2>&1

echo
echo "########## 4. 检查有没有残留的 python 后端进程 ##########"
ps -ef | grep -E "[t]ext-embeddings|[m]indie_llm_back|[p]ython.*backend" | head -5 || echo "无残留"

echo
echo "########## 5. 清空 dmesg 便于观察 ##########"
sudo dmesg -C 2>/dev/null && echo "dmesg 已清空"

echo
echo "########## 6. 用一次性容器跑 bge-m3（--rm，抓完整日志）##########"
IMG=swr.cn-south-1.myhuaweicloud.com/ascendhub/mis-tei:7.3.0-300I-Duo-aarch64
sudo docker rm -f bge-test 2>/dev/null >/dev/null
sudo timeout 180 docker run --rm --name bge-test \
  --security-opt systempaths=unconfined --user root \
  --device=/dev/davinci0 --device=/dev/davinci1 \
  --device=/dev/davinci_manager --device=/dev/devmm_svm --device=/dev/hisi_hdc \
  --shm-size=32g \
  -e TEI_NPU_DEVICE=0 \
  -v /usr/local/Ascend/driver:/usr/local/Ascend/driver \
  -v /usr/local/dcmi:/usr/local/dcmi \
  -v /usr/local/bin/npu-smi:/usr/local/bin/npu-smi \
  -v /deploy/models/test:/home/HwHiAiUser/model \
  "$IMG" /deploy/models/test/bge-m3 0.0.0.0 8000 2>&1 | tail -25

echo
echo "########## 7. 跑完后的 dmesg（找新错误）##########"
sudo dmesg -T 2>/dev/null | grep -iE "ascend|devmm|VPD|davinci" | tail -15
