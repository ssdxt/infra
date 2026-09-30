#!/bin/bash
EX=/tmp/drv_extract

echo "########## 1. 驱动源码目录结构 ##########"
ls -la $EX/driver/kernel/ 2>&1 | head -25
echo "--- dkms.conf 在哪 ---"
find $EX -name "dkms.conf" 2>/dev/null
find $EX -name "*.conf" 2>/dev/null | head -10

echo
echo "########## 2. kernel 目录下的 Makefile ##########"
ls -la $EX/driver/kernel/Makefile 2>&1
head -40 $EX/driver/kernel/Makefile 2>/dev/null

echo
echo "########## 3. 手工编译（复现真实错误）##########"
cd $EX/driver/kernel || exit 1
echo "  pwd=$(pwd)"
echo "  开始编译，最多等 8 分钟..."
timeout 480 make all KERNEL_UNAME=$(uname -r) DAVINCI_HIAI_DKMS=y TARGET_PRODUCT=mini Driver_Install_Mode=normal -j4 > /tmp/drv_build.log 2>&1
RC=$?
echo "  make 退出码: $RC"

echo
echo "########## 4. 编译错误（关键）##########"
grep -nE "error:|Error [0-9]|错误|undefined reference|No such file" /tmp/drv_build.log 2>/dev/null | head -30
echo "--- error 总数 ---"
grep -cE "error:" /tmp/drv_build.log 2>/dev/null

echo
echo "########## 5. 编译日志尾部 50 行 ##########"
tail -50 /tmp/drv_build.log 2>/dev/null

echo
echo "########## 6. 第一个出错的文件上下文 ##########"
FIRST=$(grep -nE "error:" /tmp/drv_build.log 2>/dev/null | head -1 | cut -d: -f1)
if [ -n "$FIRST" ]; then
  START=$((FIRST > 15 ? FIRST - 15 : 1))
  sed -n "${START},$((FIRST + 10))p" /tmp/drv_build.log
else
  echo "  （日志里没有 error: 关键字，看尾部）"
fi
