#!/bin/bash
L=/tmp/drv_build2.log

echo "########## 1. 日志规模 ##########"
wc -l $L
echo "--- 各类关键词计数 ---"
for k in "error:" "Error" "错误" "undefined" "No such" "cannot" "fatal" "warning:" "modpost" "LD \[M\]"; do
  printf "  %-14s %s\n" "$k" "$(grep -cE "$k" $L 2>/dev/null)"
done

echo
echo "########## 2. 唯一的 warning 是什么 ##########"
grep -nE "warning:" $L 2>/dev/null | head -10

echo
echo "########## 3. 所有 Error/错误 行（不限格式）##########"
grep -nE "Error|错误|undefined|No such file|cannot find|fatal" $L 2>/dev/null | head -40

echo
echo "########## 4. 日志最后 80 行 ##########"
tail -80 $L 2>/dev/null

echo
echo "########## 5. 关键 .o 与 .ko 是否生成 ##########"
K=/tmp/drv_extract/driver/kernel
echo "--- drv_devdrv_host.o ---"
ls -la $K/ts_drv_host/drv_devdrv_host.o 2>&1
echo "--- 已生成的 .ko 数量 ---"
find $K -name "*.ko" 2>/dev/null | wc -l
echo "--- 已生成的 .o 数量 ---"
find $K -name "*.o" 2>/dev/null | wc -l
echo "--- .ko 清单 ---"
find $K -name "*.ko" 2>/dev/null | head -30

echo
echo "########## 6. 用 -j1 重跑，让错误顺序清晰（只编最后失败的那个）##########"
cd $K || exit 1
timeout 300 make all KERNEL_UNAME=$(uname -r) DAVINCI_HIAI_DKMS=y TARGET_PRODUCT=mini Driver_Install_Mode=normal -j1 > /tmp/drv_build3.log 2>&1
echo "  退出码: $?"
echo "--- 新增日志尾部 60 行 ---"
tail -60 /tmp/drv_build3.log 2>/dev/null
echo "--- 串行编译里的错误 ---"
grep -nE "error:|Error|错误|undefined" /tmp/drv_build3.log 2>/dev/null | tail -20
