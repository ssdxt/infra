#!/bin/bash
echo "########## A) /root/.bashrc 里所有 CANN 相关行 ##########"
grep -n "Ascend\|ASCEND" /root/.bashrc

echo
echo "########## B) 三个 set_env.sh 全文 ##########"
echo "===== toolkit/set_env.sh ====="
cat /usr/local/Ascend/ascend-toolkit/set_env.sh
echo
echo "===== nnrt/set_env.sh ====="
cat /usr/local/Ascend/nnrt/set_env.sh
echo
echo "===== nnal/atb/set_env.sh （只看 export 行）====="
grep -nE "export|HOME" /usr/local/Ascend/nnal/atb/set_env.sh | head -20

echo
echo "########## C) nnrt/latest 到底是什么 ##########"
ls -la /usr/local/Ascend/nnrt/latest/ 2>&1
echo "--- readlink ---"; readlink -f /usr/local/Ascend/nnrt/latest 2>&1
echo "--- nnrt/8.1.RC1 内容 ---"; ls /usr/local/Ascend/nnrt/8.1.RC1/ 2>&1

echo
echo "########## D) toolkit 的 opp / runtime / compiler ##########"
for p in opp opp_kernel runtime compiler; do
  printf "  latest/%-12s : " "$p"
  if [ -e "/usr/local/Ascend/ascend-toolkit/latest/$p" ]; then
    echo "存在 -> $(ls /usr/local/Ascend/ascend-toolkit/latest/$p 2>/dev/null | head -4 | tr '\n' ' ')"
  else
    echo "**不存在**"
  fi
done

echo
echo "########## E) 干净环境 + 只 source toolkit，能不能 import torch_npu ##########"
env -i HOME=/root PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  bash -c '
    source /usr/local/Ascend/ascend-toolkit/set_env.sh
    echo "  ASCEND_HOME_PATH   = $ASCEND_HOME_PATH"
    echo "  ASCEND_OPP_PATH    = $ASCEND_OPP_PATH"
    echo "  ASCEND_AICPU_PATH  = $ASCEND_AICPU_PATH"
    echo "  runtime  存在? $(test -e $ASCEND_HOME_PATH/runtime   && echo YES || echo NO)"
    echo "  compiler 存在? $(test -e $ASCEND_HOME_PATH/compiler  && echo YES || echo NO)"
    echo "  opp      存在? $(test -e $ASCEND_OPP_PATH            && echo YES || echo NO)"
    echo "  ---- import torch_npu 完整报错 ----"
    /root/anaconda3/bin/python3 -c "import torch_npu; print(\">>> torch_npu OK\", torch_npu.__version__)" 2>&1 | grep -vE "^\s+(File|return|module|entrypoint|\^+)" | head -20
  '

echo
echo "########## F) toolkit 安装日志里 opp 那一段 ##########"
grep -nE "opp|install success|install failed|\[ERROR\]" /var/log/ascend_seclog/ascend_toolkit_install.log 2>/dev/null | tail -30

echo
echo "########## G) 芯片侧确认（驱动/固件没问题的话这里应正常）##########"
npu-smi info 2>&1 | head -12

echo
echo "########## H) 当前跑了几个 python/torch 进程 ##########"
ps -ef | grep -E "python3?|torch" | grep -v grep | head -10
