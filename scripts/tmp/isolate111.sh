#!/bin/bash
# 隔离测试：两个芯片 vs 不同算子，判断硬件故障范围
PY=/root/anaconda3/envs/glm4/bin/python3
source /usr/local/Ascend/ascend-toolkit/set_env.sh >/dev/null 2>&1
export ASCEND_GLOBAL_LOG_LEVEL=3
export PYTHONUNBUFFERED=1

echo "################ npu-smi info（当前驱动 24.1.0.1）################"
npu-smi info 2>&1 | head -25

for dev in 0 1; do
  echo
  echo "################===== DEVICE $dev ====="
  echo "--- T1: 仅分配张量（不动算子） ---"
  $PY -c "
import torch, torch_npu
torch.npu.set_device($dev)
x = torch.tensor([1.0,2.0,3.0], dtype=torch.float16).npu()
torch.npu.synchronize()
print('  T1 H2D copy OK ->', x.cpu().tolist())
" 2>&1 | grep -vE 'Warning|warn' | tail -5
  echo "--- T2: 取回一个 CPU 端生成的 NPU 张量（纯 D2H） ---"
  $PY -c "
import torch, torch_npu
torch.npu.set_device($dev)
x = torch.arange(8, dtype=torch.float16).npu()
y = x.cpu()
torch.npu.synchronize()
print('  T2 D2H OK ->', y.tolist())
" 2>&1 | grep -vE 'Warning|warn' | tail -5
  echo "--- T3: add 算子 ---"
  $PY -c "
import torch, torch_npu
torch.npu.set_device($dev)
x = torch.tensor([1.0,2.0,3.0], dtype=torch.float16).npu()
y = (x + 1).cpu()
print('  T3 add OK ->', y.tolist())
" 2>&1 | grep -E 'T3 add OK|RuntimeError|aicore exception|errorStr' | head -5
  echo "--- T4: mul 算子（t.py 同款） ---"
  $PY -c "
import torch, torch_npu
torch.npu.set_device($dev)
x = torch.tensor([1.0,2.0,3.0], dtype=torch.float16).npu()
y = (x * 2 + 1).cpu()
print('  T4 mul OK ->', y.tolist())
" 2>&1 | grep -E 'T4 mul OK|RuntimeError|aicore exception|errorStr' | head -5
  echo "--- T5: 大矩阵算子 ---"
  $PY -c "
import torch, torch_npu
torch.npu.set_device($dev)
a = torch.randn(512,512, dtype=torch.float16).npu()
b = torch.randn(512,512, dtype=torch.float16).npu()
c = (a @ b).cpu()
print('  T5 matmul OK ->', float(c.sum()))
" 2>&1 | grep -E 'T5 matmul OK|RuntimeError|aicore exception|errorStr' | head -5
done

echo
echo "################ 最近一次失败的 plog 摘要（aicore 相关）################"
ls -t /root/ascend/log/debug/plog/*.log 2>/dev/null | head -1 | xargs -I{} sh -c 'echo "文件: {}"; grep -iE "aicore|mte|ecc|core error" {} | tail -8'
