#!/bin/bash
# NPU availability check - layered test (device memory -> DMA copy -> kernel)
# usage: sudo bash /tmp/npu_check.sh
source /usr/local/Ascend/ascend-toolkit/set_env.sh >/dev/null 2>&1
export ASCEND_GLOBAL_LOG_LEVEL=3
PYBIN=/root/anaconda3/envs/glm4/bin/python3

echo "== board info =="
npu-smi info -t board -i 24 2>&1 | grep -iE "Product Name|Serial|Software Version|Firmware Version|Compatibility|Chip Fault"
echo

for dev in 0 1; do
  echo "=========== DEVICE $dev ==========="
  $PYBIN -c "
import torch, torch_npu
torch.npu.set_device($dev)
free,total = torch.npu.mem_get_info()
print('  [L1-MEM]  %d/%d MB' % (free//1048576, total//1048576))
x = torch.ones(16, dtype=torch.float16).npu(); torch.npu.synchronize()
print('  [L2-COPY] OK ->', x.cpu().tolist()[:3])
y = (x + 1).cpu()
print('  [L3-KERNEL] OK ->', y.cpu().tolist()[:3])
" 2>&1 | grep -E 'L1-MEM|L2-COPY|L3-KERNEL|RuntimeError|errorStr'
  echo
done

echo "== how to read =="
echo "  L1+L2 pass but L3 fails  => AICore hardware fault, RMA required (this machine)"
echo "  all three pass           => NPU usable, continue with inference deployment"
