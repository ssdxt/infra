#!/bin/bash
OPP_TK=/usr/local/Ascend/ascend-toolkit/8.1.RC1/opp
OPP_NN=/usr/local/Ascend/nnrt/8.1.RC1/opp

echo "########## 1) toolkit opp —— 真实路径，绕过软链 ##########"
du -sh $OPP_TK 2>/dev/null
echo "  文件总数      : $(find $OPP_TK -type f 2>/dev/null | wc -l)"
echo "  0 字节文件数  : $(find $OPP_TK -type f -size 0 2>/dev/null | wc -l)   <<< 关键指标"
echo "  算子 .o 总数  : $(find $OPP_TK -name '*.o' 2>/dev/null | wc -l)"
echo "  --- 0 字节文件样例（前 25 个）---"
find $OPP_TK -type f -size 0 2>/dev/null | head -25 | sed 's/^/    /'
echo "  --- op_impl 下的引擎目录（注意是 ai_core 带下划线）---"
ls $OPP_TK/built-in/op_impl/ 2>&1 | sed 's/^/    /'
echo "  --- ai_core/kernel 数量 ---"
ls $OPP_TK/built-in/op_impl/ai_core/kernel 2>/dev/null | wc -l
find $OPP_TK/built-in/op_impl/ai_core/kernel -name '*.o' 2>/dev/null | wc -l

echo
echo "########## 2) 报错里点名的两个文件 ##########"
ls -la $OPP_TK/built-in/op_impl/vector_core/tbe/config/vector_core_tbe_ops_info.json 2>&1
ls -la /usr/local/Ascend/ascend-toolkit/8.1.RC1/aarch64-linux/lib64/libconstant_folding_ops.so 2>&1

echo
echo "########## 3) aarch64-linux/lib64 下 0 字节的 .so ##########"
L64=/usr/local/Ascend/ascend-toolkit/8.1.RC1/aarch64-linux/lib64
echo "  .so 总数: $(ls $L64/*.so* 2>/dev/null | wc -l)"
echo "  0 字节 .so: $(find $L64 -maxdepth 1 -name '*.so*' -size 0 2>/dev/null | wc -l)"
find $L64 -maxdepth 1 -name '*.so*' -size 0 2>/dev/null | head -10 | sed 's/^/    /'

echo
echo "########## 4) 对照：nnrt 的 opp ##########"
du -sh $OPP_NN 2>/dev/null
echo "  文件总数    : $(find $OPP_NN -type f 2>/dev/null | wc -l)"
echo "  0 字节文件数: $(find $OPP_NN -type f -size 0 2>/dev/null | wc -l)"
echo "  op_impl 下  : $(ls $OPP_NN/built-in/op_impl/ 2>/dev/null | tr '\n' ' ')"
echo "  .o 总数     : $(find $OPP_NN -name '*.o' 2>/dev/null | wc -l)"

echo
echo "########## 5) 全盘 0 字节统计（看是局部还是普遍）##########"
for d in /usr/local/Ascend/ascend-toolkit /usr/local/Ascend/nnrt /usr/local/Ascend/nnal /usr/local/Ascend/driver /usr/local/Ascend/firmware; do
  [ -d "$d" ] || continue
  printf "  %-38s 文件=%-7s 0字节=%-6s\n" "$d" \
    "$(find $d -type f 2>/dev/null | wc -l)" \
    "$(find $d -type f -size 0 2>/dev/null | wc -l)"
done

echo
echo "########## 6) 安装日志：所有 run 的起止 ##########"
L=/var/log/ascend_seclog/ascend_toolkit_install.log
echo "  总行数: $(wc -l < $L)"
grep -a -n "install package .* start\|install success\|install failed\|process exit" $L 2>/dev/null | tail -40

echo
echo "########## 7) toolkit .run 是否支持 --extract（用于单独重装 opp）##########"
cd /deploy/driver/Ascend
./Ascend-cann-toolkit_8.1.RC1_linux-aarch64.run --help 2>&1 | grep -iE "extract|keep|install-path|full|upgrade"

echo
echo "########## 8) opp 组件安装元数据（看它自认装完没）##########"
cat $OPP_TK/ascend_install.info 2>&1 | sed 's/^/    /'
cat $OPP_TK/ascend_install.info 2>/dev/null | grep -i version
ls -la /usr/local/Ascend/ascend-toolkit/8.1.RC1/opp_kernel/ascend_install.info 2>&1
cat /usr/local/Ascend/ascend-toolkit/8.1.RC1/opp_kernel/ascend_install.info 2>&1 | sed 's/^/    /'
