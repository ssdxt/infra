#!/bin/bash
IMG=swr.cn-south-1.myhuaweicloud.com/ascendhub/mindie:1.0.0-300I-Duo-py311-openeuler24.03-lts

echo "########## 1. 先停 glm-4 避免抢占 ##########"
sudo docker stop glm-4-9b-chat 2>&1 | tail -1

echo
echo "########## 2. npu-smi 健康状态 ##########"
sudo npu-smi info 2>&1
echo "--- health chip0 ---"
sudo npu-smi info -t health -i 24 -c 0 2>&1
echo "--- health chip1 ---"
sudo npu-smi info -t health -i 24 -c 1 2>&1

echo
echo "########## 3. 最小算子测试 ##########"
cat > /tmp/t.py <<'PYEOF'
import os, sys
dev = int(sys.argv[1])
import torch, torch_npu
torch.npu.set_device(dev)
print(f">>> device {dev} 开始", flush=True)
x = torch.tensor([1.0, 2.0, 3.0], dtype=torch.float16).npu()
y = (x * 2 + 1).cpu()
print(f">>> device {dev} OK ->", y.tolist(), flush=True)
PYEOF

for d in 0 1; do
  echo "=========== TEST device $d ==========="
  sudo docker run --rm --privileged --runtime runc --entrypoint bash \
    -v /usr/local/Ascend/driver:/usr/local/Ascend/driver:ro \
    -v /dev/davinci0:/dev/davinci0 \
    -v /dev/davinci1:/dev/davinci1 \
    -v /dev/davinci_manager:/dev/davinci_manager \
    -v /dev/devmm_svm:/dev/devmm_svm \
    -v /dev/hisi_hdc:/dev/hisi_hdc \
    -v /tmp/t.py:/tmp/t.py:ro \
    -e ASCEND_GLOBAL_LOG_LEVEL=3 \
    "$IMG" -c "python3 /tmp/t.py $d" 2>&1 | grep -E ">>>|Error|error|aicore|EZ9999|retCode|507015|Traceback" | head -12
  echo
done

echo "########## 4. 恢复 ##########"
sudo docker start glm-4-9b-chat 2>&1 | tail -1
