#!/bin/bash
###############################################################################
#  修复 toolkit/opp 被中断写坏（6240 个 0 字节文件）
#  依据: 04:21:39 第二轮安装在 CANN-opp 处被中断，opp 目录 mtime=04:22
#  策略: 干净重装 toolkit（03:50 那轮证明干净装可 100% 成功，耗时约 2 分钟）
#        再补 latest/opp 软链，再重装 kernels-310p
###############################################################################
set +e
TS=$(date +%Y%m%d-%H%M%S)
TK=/usr/local/Ascend/ascend-toolkit
LATEST=$TK/latest
OPP=$TK/8.1.RC1/opp
cd /deploy/driver/Ascend || exit 1

echo "############ 阶段 0：破坏程度取证 ############"
echo "  opp 0字节: $(find $OPP -type f -size 0 2>/dev/null | wc -l) / $(find $OPP -type f 2>/dev/null | wc -l)"
echo "  .o  0字节: $(find $OPP -name '*.o' -size 0 2>/dev/null | wc -l) / $(find $OPP -name '*.o' 2>/dev/null | wc -l)"
echo "  .so 0字节: $(find $OPP -name '*.so*' -size 0 2>/dev/null | wc -l) / $(find $OPP -name '*.so*' 2>/dev/null | wc -l)"
echo "  --- 对照两个同名文件 ---"
printf "    opp/bin/setenv.bash        : "; stat -c '%s 字节' $OPP/bin/setenv.bash 2>&1
printf "    opp_kernel/bin/setenv.bash : "; stat -c '%s 字节' $LATEST/opp_kernel/bin/setenv.bash 2>&1
echo "  --- ai_core 下结构 ---"
ls $OPP/built-in/op_impl/ai_core/ 2>&1 | sed 's/^/    /'
echo "  --- 6019 个 .o 在哪 ---"
find $OPP -name '*.o' 2>/dev/null | head -3 | sed 's/^/    /'

echo
echo "############ 阶段 1：留档 ############"
find $OPP -type f -size 0 2>/dev/null > /root/opp-zerobyte-$TS.txt
echo "  0字节清单 -> /root/opp-zerobyte-$TS.txt  ($(wc -l < /root/opp-zerobyte-$TS.txt) 条)"
HASH_BEFORE=$(find $OPP -type f 2>/dev/null | wc -l)

echo
echo "############ 阶段 2：清空 toolkit 干净重装 ############"
umask 022
echo "  删除前占用: $(du -sh $TK 2>/dev/null | cut -f1)"
rm -rf $TK
echo "  删除后: $(ls -d $TK 2>&1)"
echo "  其它目录未动: $(ls /usr/local/Ascend/ | tr '\n' ' ')"
echo
echo "  --- 开始安装（约 2 分钟）---"
./Ascend-cann-toolkit_8.1.RC1_linux-aarch64.run --install --quiet < /dev/null 2>&1 | tail -25
echo "  --- 安装退出码: ${PIPESTATUS[0]} ---"

echo
echo "############ 阶段 3：补 latest/opp 软链（安装器不生成它）############"
ls -la $LATEST/ 2>&1 | grep -E " opp| ops" || echo "  确认缺失，开始补"
cd $LATEST 2>/dev/null && {
  [ -e opp ] || ln -sfn ../8.1.RC1/opp opp
  [ -e ops ] || ln -sfn ../8.1.RC1/ops ops
}
ls -la $LATEST/opp $LATEST/ops 2>&1
echo "  opp/built-in/op_impl 内容: $(ls $LATEST/opp/built-in/op_impl/ 2>/dev/null | tr '\n' ' ')"

echo
echo "############ 阶段 4：重装 310P 算子包 ############"
cd /deploy/driver/Ascend || exit 1
K=$(ls Ascend-cann-kernels-310p_*.run 2>/dev/null | head -1)
echo "  包: $K"
[ -n "$K" ] && { ./$K --install --quiet < /dev/null 2>&1 | tail -12; echo "  退出码: ${PIPESTATUS[0]}"; }

echo
echo "############ 阶段 5：完整验证 ############"
OPP2=$TK/8.1.RC1/opp
echo "  --- 5.1 完整性（0 字节必须归零）---"
echo "    opp 文件总数: $(find $OPP2 -type f 2>/dev/null | wc -l)   (修复前 $HASH_BEFORE)"
echo "    opp 0字节数 : $(find $OPP2 -type f -size 0 2>/dev/null | wc -l)   <<< 应为 0"
echo "    .o  0字节数 : $(find $OPP2 -name '*.o' -size 0 2>/dev/null | wc -l) / $(find $OPP2 -name '*.o' 2>/dev/null | wc -l)"
echo "    .so 0字节数 : $(find $OPP2 -name '*.so*' -size 0 2>/dev/null | wc -l) / $(find $OPP2 -name '*.so*' 2>/dev/null | wc -l)"
echo "    报错点名的两个文件:"
stat -c '      %s 字节  %n' $OPP2/built-in/op_impl/vector_core/tbe/config/vector_core_tbe_ops_info.json 2>&1
find $TK -name 'libconstant_folding_ops.so' -exec stat -c '      %s 字节  %n' {} \; 2>/dev/null

echo "  --- 5.2 环境变量（交互式 shell，等同新开终端）---"
bash -ic '
  echo "    ASCEND_HOME_PATH = ${ASCEND_HOME_PATH:-<空>}"
  echo "    ASCEND_OPP_PATH  = ${ASCEND_OPP_PATH:-<空>}"
  echo "    compiler : $(test -e ${ASCEND_HOME_PATH}/compiler && echo YES || echo NO)"
  echo "    runtime  : $(test -e ${ASCEND_HOME_PATH}/runtime && echo YES || echo NO)"
  echo "    opp      : $(test -e ${ASCEND_OPP_PATH} && echo YES || echo NO)"
  echo "    torch_npu: $(python3 -c "import torch_npu;print(torch_npu.__version__)" 2>&1 | tail -1)"
' 2>&1 | grep -vE "无法设定终端进程组|无任务控制"

echo "  --- 5.3 真算子下发：两张卡 ---"
for d in 0 1; do
  echo "    === chip $d ==="
  bash -ic "python3 /tmp/t.py $d" 2>&1 \
    | grep -vE "无法设定终端进程组|无任务控制" | sed 's/^/      /'
done

echo "  --- 5.4 ATB / nnal ---"
ls /usr/local/Ascend/nnal/atb/latest/ 2>&1 | head -5 | sed 's/^/    /'
source /usr/local/Ascend/nnal/atb/set_env.sh 2>/dev/null
echo "    ATB_HOME_PATH=${ATB_HOME_PATH:-<空>}"

echo "  --- 5.5 驱动侧 ---"
npu-smi info 2>&1 | sed -n '1,11p' | sed 's/^/    /'

echo
echo "############ 完成 ############"
echo "  修复前 0 字节清单: /root/opp-zerobyte-$TS.txt"
echo "  如需回滚: 本操作是「重装」，无旧状态可回滚；损坏的 opp 已无法修复。"
