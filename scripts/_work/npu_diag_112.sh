#!/bin/bash
echo "########## 0. 身份与环境 ##########"
whoami; hostname; uptime 2>&1 | head -2
cat /etc/os-release 2>/dev/null | head -3
uname -r

echo
echo "########## 1. npu-smi 原始报错（关键）##########"
which npu-smi 2>&1
echo "--- ls -la ---"
ls -la /usr/local/bin/npu-smi /usr/local/sbin/npu-smi 2>&1
echo "--- npu-smi info 原始输出 ---"
npu-smi info 2>&1 | head -30
echo "--- exit code: $? ---"

echo
echo "########## 2. NPU 设备节点 ##########"
ls -la /dev/davinci* /dev/devmm_svm /dev/hisi_hdc /dev/davinci_manager 2>&1 | head -12

echo
echo "########## 3. PCIe 上的 NPU 卡 ##########"
lspci -nn 2>/dev/null | grep -iE "19e5|huawei|ascend" || echo "  lspci 未发现华为设备"

echo
echo "########## 4. 内核模块 ##########"
lsmod 2>/dev/null | grep -iE "drv_|ascend|davinci" | head -25 || echo "  lsmod 无相关模块"
echo "--- 模块总数 ---"
lsmod 2>/dev/null | grep -icE "drv_|ascend" 

echo
echo "########## 5. Ascend 安装目录 ##########"
ls -d /usr/local/Ascend 2>/dev/null && ls /usr/local/Ascend/ 2>/dev/null
echo "--- driver 版本 ---"
cat /usr/local/Ascend/driver/version.info 2>/dev/null | head -6

echo
echo "########## 6. 相关服务 ##########"
for s in ascend-docker-runtime npu-smi ascend_device_plugin; do
  printf "  %-30s %s\n" "$s" "$(systemctl is-active $s 2>&1)"
done
echo "--- 所有 ascend 相关 unit ---"
systemctl list-units --all 2>/dev/null | grep -iE "ascend|npu|davinci" | head -10

echo
echo "########## 7. dmesg 里 NPU 相关 ##########"
dmesg -T 2>/dev/null | grep -iE "davinci|ascend|devdrv|devmm|hdc" | tail -25

echo
echo "########## 8. 设备管理器接口 ##########"
ls -la /dev/davinci_manager 2>&1
echo "--- /proc 里的 ascend 信息 ---"
ls /proc/driver/ 2>/dev/null | grep -iE "ascend|davinci" || echo "  无"
cat /proc/davinci* 2>/dev/null | head -5
