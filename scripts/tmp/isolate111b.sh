#!/bin/bash
# Isolation test: chip0 vs chip1, different op classes. ASCII output only.
source /usr/local/Ascend/ascend-toolkit/set_env.sh >/dev/null 2>&1
export ASCEND_GLOBAL_LOG_LEVEL=3
export PYTHONUNBUFFERED=1
PYBIN=/root/anaconda3/envs/glm4/bin/python3

echo "== python/torch versions =="
$PYBIN -c "import torch,torch_npu;print('torch',torch.__version__,'torch_npu',torch_npu.__version__,'npu_count',torch.npu.device_count())" 2>&1 | tail -3

for dev in 0 1; do
  echo
  echo "=========== DEVICE $dev ==========="

  echo "--- T1 H2D only (no kernel) ---"
  $PYBIN -c "
import torch, torch_npu
torch.npu.set_device($dev)
x = torch.tensor([1.0,2.0,3.0], dtype=torch.float16).npu()
torch.npu.synchronize()
print('  T1 H2D OK ->', x.cpu().tolist())
" 2>&1 | grep -E 'T1 H2D OK|RuntimeError|errorStr' | head -3

  echo "--- T2 add kernel ---"
  $PYBIN -c "
import torch, torch_npu
torch.npu.set_device($dev)
x = torch.tensor([1.0,2.0,3.0], dtype=torch.float16).npu()
y = (x + 1).cpu()
print('  T2 ADD OK ->', y.tolist())
" 2>&1 | grep -E 'T2 ADD OK|RuntimeError|errorStr' | head -3

  echo "--- T3 mul kernel (same as /tmp/t.py) ---"
  $PYBIN -c "
import torch, torch_npu
torch.npu.set_device($dev)
x = torch.tensor([1.0,2.0,3.0], dtype=torch.float16).npu()
y = (x * 2 + 1).cpu()
print('  T3 MUL OK ->', y.tolist())
" 2>&1 | grep -E 'T3 MUL OK|RuntimeError|errorStr' | head -3

  echo "--- T4 matmul 512x512 ---"
  $PYBIN -c "
import torch, torch_npu
torch.npu.set_device($dev)
a = torch.randn(512,512, dtype=torch.float16).npu()
b = torch.randn(512,512, dtype=torch.float16).npu()
c = (a @ b).cpu()
print('  T4 MATMUL OK ->', round(float(c.sum()),3))
" 2>&1 | grep -E 'T4 MATMUL OK|RuntimeError|errorStr' | head -3
done

echo
echo "== npu-smi health after tests =="
npu-smi info 2>&1 | sed -n '5,20p'
