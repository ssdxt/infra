#!/bin/bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh >/dev/null 2>&1
export ASCEND_GLOBAL_LOG_LEVEL=3
PY=/root/anaconda3/envs/glm4/bin/python
T=/tmp/dsh_npu_test
rm -rf $T && mkdir -p $T
cat > $T/t.py <<'PYEOF'
import sys
import torch, torch_npu
d = int(sys.argv[1])
torch.npu.set_device(d)
x = torch.tensor([1.0, 2.0, 3.0], dtype=torch.float16).npu()
y = (x * 2 + 1).cpu()
print("RESULT OK ->", y.tolist())
PYEOF

for d in 0 1; do
  echo "--- device $d ---"
  $PY $T/t.py $d 2>&1 | grep -aE 'RESULT OK|aicore|errorStr|Error|error' | head -6
done
