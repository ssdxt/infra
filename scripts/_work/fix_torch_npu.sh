#!/bin/bash
###############################################################################
#  修复 torch_npu 无法 import（111 机器）
#   问题A: /root/.bashrc 里 nnrt/set_env.sh 排在最后，覆盖 toolkit 布局
#   问题B: toolkit/latest/opp 软链缺失 -> ASCEND_OPP_PATH 指向不存在的目录
#  可回滚: .bashrc 备份在同目录 .bak-<时间戳>
###############################################################################
set +e
TS=$(date +%Y%m%d-%H%M%S)
TK=/usr/local/Ascend/ascend-toolkit
LATEST=$TK/latest

echo "=== 0) 备份 ==="
cp -a /root/.bashrc /root/.bashrc.bak-$TS && echo "  .bashrc -> /root/.bashrc.bak-$TS"
ls -la $LATEST > /root/latest-before-$TS.txt && echo "  latest 清单 -> /root/latest-before-$TS.txt"
readlink -f $LATEST/opp > /root/opp-link-before-$TS.txt 2>&1
cat /root/opp-link-before-$TS.txt | sed 's/^/  opp 修复前: /'

echo
echo "=== 1) .bashrc 结构（看交互式早退守卫在第几行）==="
grep -nE "not running interactively|case \\\$- in|^[[:space:]]*return" /root/.bashrc | head
echo "--- 早退守卫前的 CANN 行? ---"
grep -n "Ascend" /root/.bashrc

echo
echo "=== 2) 补 opp / ops 软链 ==="
cd $LATEST || exit 1
ln -sfn ../8.1.RC1/opp opp
ln -sfn ../8.1.RC1/ops ops
ls -la opp ops
echo "  opp 是目录? $(test -d opp && echo YES || echo NO)"
echo "  opp/built-in 存在? $(test -d opp/built-in && echo YES || echo NO)"
echo "  opp/built-in/op_impl 内容:"
ls opp/built-in/op_impl/ 2>&1 | sed 's/^/    /'

echo
echo "=== 3) 注释 .bashrc 里的 nnrt ==="
sed -i 's|^source /usr/local/Ascend/nnrt/set_env.sh|#source /usr/local/Ascend/nnrt/set_env.sh   # 与 toolkit 布局冲突，已禁用|' /root/.bashrc
grep -n "Ascend" /root/.bashrc

echo
echo "=== 4) 环境验证（交互式 shell，等同新开终端）==="
bash -ic '
  echo "  ASCEND_HOME_PATH  = ${ASCEND_HOME_PATH:-<空>}"
  echo "  ASCEND_OPP_PATH   = ${ASCEND_OPP_PATH:-<空>}"
  echo "  ASCEND_AICPU_PATH = ${ASCEND_AICPU_PATH:-<空>}"
  echo "  compiler: $(test -e ${ASCEND_HOME_PATH}/compiler && echo YES || echo NO)"
  echo "  runtime : $(test -e ${ASCEND_HOME_PATH}/runtime  && echo YES || echo NO)"
  echo "  opp     : $(test -e ${ASCEND_OPP_PATH}           && echo YES || echo NO)"
  echo "  python3 : $(command -v python3)"
' 2>&1 | grep -vE "无法设定终端进程组|此 shell 中无任务控制|bash: cannot set terminal"

echo
echo "=== 5) import torch_npu ==="
bash -ic 'python3 -c "import torch, torch_npu; print(\"  torch\", torch.__version__, \"| torch_npu\", torch_npu.__version__)"' 2>&1 \
  | grep -vE "无法设定终端进程组|此 shell 中无任务控制"

echo
echo "=== 6) /tmp/t.py 真算子下发测试（两张卡）==="
for d in 0 1; do
  echo "--- chip $d ---"
  bash -ic "python3 /tmp/t.py $d" 2>&1 | grep -vE "无法设定终端进程组|此 shell 中无任务控制" | sed 's/^/  /'
  echo "  (退出码 ${PIPESTATUS[0]})"
done

echo
echo "=== 7) 算子库核查（AI Core .o 是否真的落盘）==="
echo "  opp 总大小: $(du -sh $LATEST/opp 2>/dev/null | cut -f1)"
echo "  aicore/kernel 下 .o 数量: $(ls $LATEST/opp/built-in/op_impl/aicore/kernel 2>/dev/null | wc -l)"
echo "  aicore/kernel 前几个:"
ls $LATEST/opp/built-in/op_impl/aicore/kernel 2>/dev/null | head -5 | sed 's/^/    /'
echo "  整个 opp 下 .o 总数: $(find $LATEST/opp -name '*.o' 2>/dev/null | wc -l)"
echo "  opp_kernel 目录内容:"
ls $LATEST/opp_kernel/ 2>&1 | sed 's/^/    /'

echo
echo "=== 8) 备用路线：不依赖 .bashrc，显式 source ==="
env -i HOME=/root PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  bash -c 'source /usr/local/Ascend/ascend-toolkit/set_env.sh; python3 /tmp/t.py 0' 2>&1 | tail -5 | sed 's/^/  /'

echo
echo "=== 9) 驱动侧对照 ==="
npu-smi info 2>&1 | sed -n '1,12p' | sed 's/^/  /'

echo
echo "===== 完成。回滚方法 ====="
echo "  cp -a /root/.bashrc.bak-$TS /root/.bashrc"
echo "  rm -f $LATEST/opp $LATEST/ops"
