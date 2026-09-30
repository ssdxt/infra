#!/bin/bash
echo "########## 1. 操作系统 ##########"
cat /etc/os-release 2>/dev/null | grep -E "^(NAME|VERSION|PRETTY_NAME|ID|VERSION_ID)="
echo "内核: $(uname -r)"
echo "架构: $(uname -m)"
echo "主机名: $(hostname)"

echo
echo "########## 2. CPU / 内存 ##########"
lscpu 2>/dev/null | grep -E "^(型号名称|Model name|架构|Architecture|CPU\(s\)|每个插槽的核心|Core\(s\) per socket):" | head -6
echo "内存: $(free -h | awk '/Mem:/{print $2}')"

echo
echo "########## 3. 驱动版本文件 ##########"
sudo cat /usr/local/Ascend/driver/version.info 2>&1 | head -10

echo
echo "########## 4. CANN 版本 ##########"
ls -d /usr/local/Ascend/ascend-toolkit/*/ 2>/dev/null
cat /usr/local/Ascend/ascend-toolkit/latest/version.cfg 2>/dev/null | head -5
ls -d /usr/local/Ascend/cann-* 2>/dev/null

echo
echo "########## 5. npu-smi 版本/健康 ##########"
sudo npu-smi info -t version -i 24 2>&1 | head -20
echo "--- 温度/功耗/ECC ---"
sudo npu-smi info -t temp -i 24 -c 0 2>&1 | head -5
sudo npu-smi info -t health -i 24 -c 0 2>&1 | head -5
sudo npu-smi info -t health -i 24 -c 1 2>&1 | head -5

echo
echo "########## 6. 当前 npu-smi info ##########"
sudo npu-smi info 2>&1 | head -22

echo
echo "########## 7. PCIe 链路 ##########"
sudo lspci -vv -s 0b:00.0 2>/dev/null | grep -iE "LnkCap|LnkSta|Region|Kernel driver" | head -10
