#!/bin/bash
K=/tmp/drv_extract/driver/kernel

echo "########## 1. 确认 -Werror 是哪来的 ##########"
echo "--- 内核配置里的 CONFIG_WERROR ---"
grep -iE "CONFIG_WERROR" /boot/config-$(uname -r) 2>/dev/null || echo "  没找到 CONFIG_WERROR"
echo "--- 内核 Makefile 里的 Werror ---"
grep -nE "Werror" /usr/src/linux-headers-$(uname -r)/Makefile 2>/dev/null | head -5
echo "--- 驱动 Makefile 里的 Werror ---"
grep -nE "Werror|KCFLAGS|ccflags" $K/Makefile 2>/dev/null | head -10

echo
echo "########## 2. 出问题的源码上下文（第 2295-2315 行）##########"
sed -n '2295,2315p' $K/svmdrv/pmaster/devmm_proc_mem_copy.c 2>/dev/null

echo
echo "########## 3. 用 KCFLAGS 覆盖该警告，重新编译 ##########"
export KCFLAGS="-Wno-error=maybe-uninitialized -Wno-maybe-uninitialized"
echo "  KCFLAGS=$KCFLAGS"
cd $K || exit 1
timeout 600 make all KERNEL_UNAME=$(uname -r) DAVINCI_HIAI_DKMS=y TARGET_PRODUCT=mini Driver_Install_Mode=normal -j4 > /tmp/drv_build4.log 2>&1
RC=$?
echo "  make 退出码: $RC"

echo
echo "########## 4. 结果统计 ##########"
echo "  error 条数: $(grep -cE 'error:|错误：' /tmp/drv_build4.log 2>/dev/null)"
echo "  生成的 .ko 数量: $(find $K -name '*.ko' 2>/dev/null | wc -l)"
echo "--- .ko 清单 ---"
find $K -name "*.ko" 2>/dev/null | sed 's|.*/kernel/||' | sort
echo
echo "--- 日志尾部 25 行 ---"
tail -25 /tmp/drv_build4.log 2>/dev/null

echo
echo "########## 5. 若仍有错，看看是什么 ##########"
grep -nE "error:|错误：|Error" /tmp/drv_build4.log 2>/dev/null | head -15
