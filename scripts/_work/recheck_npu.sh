#!/bin/bash
echo "########## 0. 时点与运行时长 ##########"
date
echo "uptime: $(uptime 2>&1)"
echo "hostname: $(hostname)"
echo "IP: $(ip -4 addr show 2>/dev/null | grep -oP 'inet \K[\d.]+' | grep -v 127.0.0.1 | tr '\n' ' ')"

echo
echo "########## 1. PCIe 上有没有华为卡（最关键）##########"
lspci -nn 2>/dev/null | grep -iE "19e5|huawei|ascend" && echo "  >>> 卡出现了！" || echo "  >>> 仍然没有华为设备"
echo "--- 全部 PCIe 设备数: $(lspci 2>/dev/null | wc -l) ---"
echo "--- 有没有 0b: 总线 ---"
lspci 2>/dev/null | grep -i "^0b:" || echo "  无 0b: 总线设备"
echo "--- sysfs ---"
ls /sys/bus/pci/devices/ 2>/dev/null | grep -i "0b:" || echo "  sysfs 里无 0b:*"

echo
echo "########## 2. NPU 设备节点 ##########"
ls -la /dev/ 2>/dev/null | grep -iE "davinci|devmm|hisi|svm" || echo "  无 NPU 设备节点"

echo
echo "########## 3. npu-smi info ##########"
npu-smi info 2>&1 | head -25

echo
echo "########## 4. 内核模块 ##########"
lsmod 2>/dev/null | grep -iE "drv_|ascend|davinci" | head -20
echo "  模块数: $(lsmod 2>/dev/null | grep -icE 'drv_|ascend')"
echo "--- 关键的 PCIe 设备驱动是否加载 ---"
lsmod 2>/dev/null | grep -E "drv_devdrv_host|drv_pcie_host" || echo "  drv_devdrv_host / drv_pcie_host 均未加载"

echo
echo "########## 5. host_sys_init 最新记录 ##########"
tail -20 /var/log/ascend_seclog/ascend_run_servers.log 2>/dev/null

echo
echo "########## 6. dmesg 里 NPU 相关（本次启动）##########"
dmesg -T 2>/dev/null | grep -iE "ascend|davinci|devdrv|devmm|hdc" | tail -20 || echo "  无"

echo
echo "########## 7. 服务状态 ##########"
systemctl is-active host_sys_init 2>&1 | sed 's/^/  host_sys_init: /'
npu-smi info -t board -i 0 2>&1 | head -5

echo
echo "########## 8. 对照：之前正常时的记录 ##########"
echo "--- ascend_run_servers.log 里 davinci_num=2 的最后时间 ---"
grep "davinci_num=2" /var/log/ascend_seclog/ascend_run_servers.log 2>/dev/null | tail -3
echo "--- 归零的时间 ---"
grep "davinci_num=0" /var/log/ascend_seclog/ascend_run_servers.log 2>/dev/null | tail -3
