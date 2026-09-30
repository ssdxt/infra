#!/bin/bash
DRV=/deploy/driver/Ascend/Ascend-hdk-310p-npu-driver_24.1.0.1_linux-aarch64.run
EX=/tmp/drv_extract

echo "########## 1. 编译环境前提 ##########"
echo "--- 内核头文件 ---"
ls -d /lib/modules/$(uname -r)/build 2>&1
ls -ld /lib/modules/$(uname -r)/build 2>&1
echo "--- build/Makefile 是否存在 ---"
ls -la /lib/modules/$(uname -r)/build/Makefile 2>&1
echo "--- gcc ---"
gcc --version 2>&1 | head -2
echo "--- make ---"
make --version 2>&1 | head -1
echo "--- dkms ---"
dkms --version 2>&1

echo
echo "########## 2. 驱动安装包 ##########"
ls -la $DRV 2>&1
echo "--- /deploy/driver/Ascend 目录 ---"
ls -la /deploy/driver/Ascend/ 2>&1

echo
echo "########## 3. 残留的 dkms 源码/状态 ##########"
ls -la /usr/src/ 2>/dev/null | grep -i davinci || echo "  /usr/src 下无 davinci 残留"
ls -d /var/lib/dkms/davinci_ascend 2>&1
dkms status 2>&1 | grep -i davinci || echo "  dkms 状态里无 davinci"

echo
echo "########## 4. 解压驱动包（--noexec --extract）##########"
rm -rf $EX
mkdir -p $EX
cd /tmp || exit 1
"$DRV" --noexec --extract=$EX 2>&1 | tail -5
echo "--- 解压结果 ---"
ls -la $EX/ 2>&1 | head -20
echo "--- 找 dkms.conf / 源码目录 ---"
find $EX -maxdepth 3 -name "dkms.conf" 2>/dev/null
find $EX -maxdepth 3 -name "Makefile" 2>/dev/null | head -5
find $EX -maxdepth 2 -type d 2>/dev/null | head -15

echo
echo "########## 5. 找驱动源码里的 .c 文件数量（确认源码完整）##########"
find $EX -name "*.c" 2>/dev/null | wc -l | sed 's/^/  .c 文件数: /'
find $EX -name "*.h" 2>/dev/null | wc -l | sed 's/^/  .h 文件数: /'
