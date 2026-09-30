#!/bin/bash
echo "########## 1. rc.local 状态（dmesg 报它被跳过）##########"
ls -la /etc/rc.d/rc.local /etc/rc.local 2>&1
echo "--- 内容 ---"
cat /etc/rc.d/rc.local 2>/dev/null || cat /etc/rc.local 2>/dev/null || echo "  文件不存在"

echo
echo "########## 2. host_sys_init 脚本（LSB 服务，负责 davinci 设备）##########"
ls -la /etc/init.d/host_sys_init 2>&1
echo "--- 内容前 40 行 ---"
head -40 /etc/init.d/host_sys_init 2>/dev/null
echo "--- 它实际调用的脚本 ---"
grep -oE "/usr/local/Ascend/[a-zA-Z0-9_./-]+" /etc/init.d/host_sys_init 2>/dev/null | sort -u

echo
echo "########## 3. Ascend 自带的 init 脚本 ##########"
for f in /usr/local/Ascend/host_sys_init.sh /usr/local/Ascend/host_services_setup.sh; do
  echo "--- $f ---"
  ls -la $f 2>&1
  head -25 $f 2>/dev/null
done

echo
echo "########## 4. 驱动 ko 文件位置 ##########"
find /usr/local/Ascend/driver -maxdepth 3 -type d 2>/dev/null | head -15
echo "--- ko 文件 ---"
find /usr/local/Ascend/driver -name "*.ko" 2>/dev/null | head -20
echo "  ko 总数: $(find /usr/local/Ascend/driver -name '*.ko' 2>/dev/null | wc -l)"

echo
echo "########## 5. 尝试 PCIe 重新扫描（安全、可逆）##########"
echo "--- rescan 前：查华为设备 ---"
lspci -nn 2>/dev/null | grep -iE "19e5|huawei" || echo "  无"
echo "--- 执行 rescan ---"
if [ -w /sys/bus/pci/rescan ]; then
  echo 1 > /sys/bus/pci/rescan
  echo "  rescan 已触发"
else
  echo "  /sys/bus/pci/rescan 不可写（当前用户: $(whoami)）"
fi
sleep 3
echo "--- rescan 后：查华为设备 ---"
lspci -nn 2>/dev/null | grep -iE "19e5|huawei" || echo "  仍然无"
echo "--- rescan 后 PCIe 设备数 ---"
ls /sys/bus/pci/devices/ 2>/dev/null | wc -l
echo "--- 有没有 0b: ---"
ls /sys/bus/pci/devices/ 2>/dev/null | grep -i "0b:" || echo "  没有 0b:*"

echo
echo "########## 6. rescan 后 dmesg 新增 ##########"
dmesg -T 2>/dev/null | tail -15

echo
echo "########## 7. 尝试 modprobe 驱动模块（若卡存在）##########"
modprobe drv_davinci_intf_host 2>&1 && echo "  modprobe 成功" || echo "  modprobe 失败"
sleep 2
lsmod 2>/dev/null | grep -cE "drv_|ascend" | sed 's/^/  ascend 模块数: /'
ls -la /dev/davinci* 2>&1 | head -6
