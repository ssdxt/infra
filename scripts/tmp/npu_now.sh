#!/bin/bash
echo "===== 1. docker 容器清单 ====="
sudo docker ps -a --format '{{.Names}} | {{.Status}} | {{.Image}}' | head -20

echo
echo "===== 2. 最小 NPU 算子测试（宿主机，两芯片）====="
sudo bash -c 'source /usr/local/Ascend/ascend-toolkit/set_env.sh >/dev/null 2>&1
export ASCEND_GLOBAL_LOG_LEVEL=3
for d in 0 1; do
  echo "--- device $d ---"
  /root/anaconda3/envs/glm4/bin/python -c "
import torch, torch_npu
torch.npu.set_device($d)
x = torch.tensor([1.0,2.0,3.0], dtype=torch.float16).npu()
y = (x*2+1).cpu()
print(\"RESULT OK ->\", y.tolist())
" 2>&1 | grep -aE 'RESULT OK|aicore|errorStr|Error|RuntimeError' | head -6
done'

echo
echo "===== 3. 驱动/固件 ====="
grep -E '^Version=' /usr/local/Ascend/driver/version.info
sudo npu-smi info -t board -i 24 2>&1 | grep -E 'Firmware|Software|Chip Fault'
