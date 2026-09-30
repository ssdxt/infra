#!/bin/bash
echo "########## 1) 当前 shell 的 CANN 环境变量 ##########"
for v in ASCEND_HOME_PATH ASCEND_COMPILER_PATH ASCEND_OPP_PATH ASCEND_AICPU_PATH \
         ASCEND_TOOLKIT_HOME ASCEND_NNAL_HOME ASCEND_RT_VISIBLE_DEVICES; do
  printf "  %-26s = %s\n" "$v" "${!v:-<未设置>}"
done

echo
echo "########## 2) /usr/local/Ascend 下有哪些布局 ##########"
ls -la /usr/local/Ascend/ 2>&1
echo "--- nnrt 是否存在 ---"
ls -la /usr/local/Ascend/nnrt 2>&1
echo "--- ascend-toolkit/latest 顶层 ---"
ls /usr/local/Ascend/ascend-toolkit/latest/ 2>&1
echo "--- toolkit 有没有 compiler 目录 ---"
ls -d /usr/local/Ascend/ascend-toolkit/latest/compiler 2>&1

echo
echo "########## 3) 谁把 ASCEND_COMPILER_PATH 设成了 nnrt ##########"
grep -rn "ASCEND_COMPILER_PATH\|nnrt" \
  /root/.bashrc /root/.profile /etc/profile /etc/bash.bashrc \
  /etc/profile.d/*.sh /usr/local/Ascend/*/set_env.sh 2>/dev/null | head -20
echo "--- 全盘搜 set_env.sh ---"
ls -la /usr/local/Ascend/*/set_env.sh /usr/local/Ascend/*/*/set_env.sh 2>/dev/null

echo
echo "########## 4) torch_npu 判定逻辑原文（npu_intercept.py 40-75 行）##########"
sed -n '35,80p' /root/anaconda3/lib/python3.11/site-packages/torch_npu/utils/npu_intercept.py 2>&1

echo
echo "########## 5) torch / torch_npu 版本 ##########"
/root/anaconda3/bin/pip3 list 2>/dev/null | grep -iE "^torch|^numpy|^decorator|^attrs|^psutil|^scipy|^absl|^cloudpickle"
echo "--- dist-info ---"
ls -d /root/anaconda3/lib/python3.11/site-packages/torch_npu*dist-info /root/anaconda3/lib/python3.11/site-packages/torch*dist-info 2>/dev/null

echo
echo "########## 6) /tmp/t.py 内容 ##########"
cat /tmp/t.py 2>&1

echo
echo "########## 7) 只 import torch（不碰 npu）能否成功 ##########"
/root/anaconda3/bin/python3 -c "import torch; print('torch', torch.__version__)" 2>&1 | tail -3

echo
echo "########## 8) 装了 toolkit 环境后再 import torch_npu ##########"
source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null
echo "  source 后 ASCEND_HOME_PATH=$ASCEND_HOME_PATH"
echo "  source 后 ASCEND_COMPILER_PATH=${ASCEND_COMPILER_PATH:-<仍未设置>}"
/root/anaconda3/bin/python3 -c "import torch, torch_npu; print('OK', torch_npu.__version__)" 2>&1 | tail -6

echo
echo "########## 9) toolkit 里 compiler 目录实况 ##########"
ls /usr/local/Ascend/ascend-toolkit/latest/compiler/ 2>&1 | head
ls -d /usr/local/Ascend/ascend-toolkit/latest/compiler/ccec_compiler 2>&1

echo
echo "########## 10) nnal / nnrt 是否装过 ##########"
ls -la /usr/local/Ascend/ 2>&1 | grep -iE "nnal|nnrt|atb"
