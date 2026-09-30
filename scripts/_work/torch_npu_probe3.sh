#!/bin/bash
echo "########## 1) toolkit 目录：latest 是软链还是真目录 ##########"
ls -la /usr/local/Ascend/ascend-toolkit/
echo "--- latest 内部（看哪些是 -> 软链）---"
ls -la /usr/local/Ascend/ascend-toolkit/latest/

echo
echo "########## 2) 版本目录 8.1.RC1 里到底有没有 opp ##########"
ls -la /usr/local/Ascend/ascend-toolkit/8.1.RC1/ 2>&1
echo "--- 单独看 opp ---"
ls -ld /usr/local/Ascend/ascend-toolkit/8.1.RC1/opp 2>&1
ls /usr/local/Ascend/ascend-toolkit/8.1.RC1/opp/ 2>&1 | head

echo
echo "########## 3) 各组件占用（看 opp 是不是装了一半）##########"
du -sh /usr/local/Ascend/ascend-toolkit/8.1.RC1/* 2>/dev/null | sort -h

echo
echo "########## 4) 磁盘空间（opp 很大，满了也会装不上）##########"
df -h /usr/local /var /tmp 2>&1

echo
echo "########## 5) toolkit 安装日志（二进制，用 -a）##########"
echo "--- 抓 opp / failed / success ---"
grep -a -oE "CANN-[a-z_]+-[0-9.]+-linux\.aarch64\.run[^\"]{0,60}(success|failed)?|install package [^ ]+ (start|success|failed)|\[ERROR\][^\"]{0,120}" \
  /var/log/ascend_seclog/ascend_toolkit_install.log 2>/dev/null | tail -40
echo "--- 文件类型与末尾 ---"
file /var/log/ascend_seclog/ascend_toolkit_install.log
tail -c 3000 /var/log/ascend_seclog/ascend_toolkit_install.log | strings | tail -25

echo
echo "########## 6) 对照：nnrt 的 opp 是完整的 ##########"
ls /usr/local/Ascend/nnrt/8.1.RC1/opp/ 2>&1
echo "--- nnrt opp 的算子实现 ---"
ls /usr/local/Ascend/nnrt/8.1.RC1/opp/built-in/op_impl/ 2>&1
du -sh /usr/local/Ascend/nnrt/8.1.RC1/opp 2>/dev/null

echo
echo "########## 7) toolkit 侧 opp_kernel 内容（来自 kernels-310p）##########"
ls /usr/local/Ascend/ascend-toolkit/latest/opp_kernel/ 2>&1
ls /usr/local/Ascend/ascend-toolkit/latest/opp_kernel/bin/ 2>&1 | head

echo
echo "########## 8) 诊断验证：ASCEND_HOME_PATH=toolkit + ASCEND_OPP_PATH=nnrt/opp ##########"
env -i HOME=/root PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  bash -c '
    export ASCEND_HOME_PATH=/usr/local/Ascend/ascend-toolkit/latest
    export ASCEND_OPP_PATH=/usr/local/Ascend/nnrt/latest/opp
    export LD_LIBRARY_PATH=$ASCEND_HOME_PATH/lib64:$LD_LIBRARY_PATH
    echo "  compiler: $(test -e $ASCEND_HOME_PATH/compiler && echo YES || echo NO)"
    echo "  runtime : $(test -e $ASCEND_HOME_PATH/runtime  && echo YES || echo NO)"
    echo "  opp     : $(test -e $ASCEND_OPP_PATH           && echo YES || echo NO)"
    echo "  ---- import 测试 ----"
    /root/anaconda3/bin/python3 -c "import torch, torch_npu; print(\">>> torch_npu OK\", torch_npu.__version__)" 2>&1 | tail -4
  '

echo
echo "########## 9) 现在 .bashrc 里的顺序问题复现 ##########"
bash -lc 'echo "  ASCEND_HOME_PATH=$ASCEND_HOME_PATH"; echo "  ASCEND_OPP_PATH=$ASCEND_OPP_PATH"' 2>&1
