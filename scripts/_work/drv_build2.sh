#!/bin/bash
EX=/tmp/drv_extract
K=$EX/driver/kernel

echo "########## 1. Makefile_mini1910p 内容（前 50 行）##########"
head -50 $K/Makefile_mini1910p 2>&1

echo
echo "########## 2. dkms_mini1910p.conf 内容 ##########"
cat $K/dkms_mini1910p.conf 2>&1 | head -40

echo
echo "########## 3. 按安装脚本的做法改名 ##########"
cp -f $K/Makefile_mini1910p $K/Makefile
cp -f $K/dkms_mini1910p.conf $K/dkms.conf
echo "  已复制 Makefile_mini1910p -> Makefile"
echo "  已复制 dkms_mini1910p.conf -> dkms.conf"

echo
echo "########## 4. 手工编译（这次应该能跑起来）##########"
cd $K || exit 1
echo "  开始，最多等 10 分钟..."
timeout 600 make all KERNEL_UNAME=$(uname -r) DAVINCI_HIAI_DKMS=y TARGET_PRODUCT=mini Driver_Install_Mode=normal -j4 > /tmp/drv_build2.log 2>&1
RC=$?
echo "  make 退出码: $RC"

echo
echo "########## 5. 编译错误统计 ##########"
echo "  error: 条数 = $(grep -cE 'error:' /tmp/drv_build2.log 2>/dev/null)"
echo "  warning 条数 = $(grep -cE 'warning:' /tmp/drv_build2.log 2>/dev/null)"
echo "--- 错误列表 ---"
grep -nE "error:|Error [0-9]+" /tmp/drv_build2.log 2>/dev/null | head -25

echo
echo "########## 6. 日志尾部 40 行 ##########"
tail -40 /tmp/drv_build2.log 2>/dev/null

echo
echo "########## 7. 第一个错误的上下文 ##########"
FIRST=$(grep -nE "error:" /tmp/drv_build2.log 2>/dev/null | head -1 | cut -d: -f1)
if [ -n "$FIRST" ]; then
  START=$((FIRST > 20 ? FIRST - 20 : 1))
  sed -n "${START},$((FIRST + 12))p" /tmp/drv_build2.log
else
  echo "  无 error: 关键字"
fi
