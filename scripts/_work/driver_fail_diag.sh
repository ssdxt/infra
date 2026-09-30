#!/bin/bash
echo "########## 0. 环境 ##########"
hostname; uname -r; cat /etc/os-release 2>/dev/null | head -3
echo "uptime: $(uptime 2>&1)"

echo
echo "########## 1. 驱动安装日志里的错误段（关键）##########"
grep -nE "ERROR|error|failed|Failed" /var/log/ascend_seclog/ascend_install.log 2>/dev/null | tail -40

echo
echo "########## 2. 安装日志尾部 60 行 ##########"
tail -60 /var/log/ascend_seclog/ascend_install.log 2>/dev/null

echo
echo "########## 3. DKMS 状态 ##########"
dkms status 2>&1
echo "--- /var/lib/dkms 结构 ---"
ls -la /var/lib/dkms/ 2>/dev/null
find /var/lib/dkms -maxdepth 3 -type d 2>/dev/null | head -20

echo
echo "########## 4. DKMS 编译日志 make.log（真正的报错在这）##########"
for f in $(find /var/lib/dkms -name "make.log" 2>/dev/null | head -3); do
  echo "===== $f ====="
  tail -60 "$f" 2>&1
done

echo
echo "########## 5. 内核头文件 / 编译环境 ##########"
echo "--- 内核头文件目录 ---"
ls -d /lib/modules/$(uname -r)/build /usr/src/kernels/$(uname -r) 2>&1
echo "--- gcc ---"
gcc --version 2>&1 | head -2
echo "--- dkms ---"
which dkms && dkms --version 2>&1 | head -2
echo "--- make ---"
which make

echo
echo "########## 6. 当前 NPU 状态 ##########"
ls -la /dev/davinci* /dev/devmm_svm /dev/hisi_hdc 2>&1 | head -8
echo "--- lspci ---"
lspci -nn 2>/dev/null | grep -iE "19e5|huawei" || echo "  未发现华为设备"
echo "--- 模块 ---"
lsmod 2>/dev/null | grep -cE "drv_|ascend" | sed 's/^/  ascend 模块数: /'

echo
echo "########## 7. 驱动包与源码位置 ##########"
ls -la /usr/local/Ascend/driver/ 2>/dev/null | head -10
echo "--- dkms 源码 ---"
find /usr/src -maxdepth 2 -iname "*ascend*" -o -maxdepth 2 -iname "*drv*" 2>/dev/null | head -10

echo
echo "########## 8. operation.log（安装操作记录）##########"
tail -25 /var/log/ascend_seclog/operation.log 2>/dev/null
