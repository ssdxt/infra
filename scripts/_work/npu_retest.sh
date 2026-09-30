#!/bin/bash
IMG=swr.cn-south-1.myhuaweicloud.com/ascendhub/mindie:1.0.0-300I-Duo-py311-openeuler24.03-lts

echo "########## 1. 停 glm-4、清残留 ##########"
sudo timeout 40 docker update --restart=no glm-4-9b-chat 2>&1 | tail -1
sudo timeout 60 docker stop -t 5 glm-4-9b-chat 2>&1 | tail -1
sudo timeout 30 docker rm -f glm-4-9b-chat 2>&1 | tail -1
sudo pkill -9 -f npu-smi 2>/dev/null
sudo pkill -9 -f mindie_llm_back 2>/dev/null
sleep 3
echo "--- 剩余进程 ---"
sudo npu-smi info 2>&1 | sed -n '/Process id/,$p'

echo
echo "########## 2. 复位后测最小算子 ##########"
cat > /tmp/t.py <<'PYEOF'
import sys
dev = int(sys.argv[1])
import torch, torch_npu
torch.npu.set_device(dev)
print(f">>> device {dev} set_device OK", flush=True)
x = torch.tensor([1.0, 2.0, 3.0], dtype=torch.float16).npu()
y = (x * 2 + 1).cpu()
print(f">>> device {dev} RESULT OK ->", y.tolist(), flush=True)
PYEOF

for d in 0 1; do
  echo "=========== device $d ==========="
  sudo timeout 120 docker run --rm --privileged --runtime runc --entrypoint bash \
    -v /usr/local/Ascend/driver:/usr/local/Ascend/driver:ro \
    -v /dev/davinci0:/dev/davinci0 -v /dev/davinci1:/dev/davinci1 \
    -v /dev/davinci_manager:/dev/davinci_manager \
    -v /dev/devmm_svm:/dev/devmm_svm -v /dev/hisi_hdc:/dev/hisi_hdc \
    -v /tmp/t.py:/tmp/t.py:ro \
    -e ASCEND_GLOBAL_LOG_LEVEL=3 \
    "$IMG" -c "python3 /tmp/t.py $d" 2>&1 | grep -E ">>>|aicore|errorStr|coreId|retCode|507015|MTE|Error" | head -8
  echo
done
