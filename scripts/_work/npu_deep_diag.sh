#!/bin/bash
echo "########## 1. lspci 完整列表（找 0b:00.0）##########"
lspci -nn 2>&1 | head -40

echo
echo "########## 2. sysfs 里 PCIe 设备 ##########"
echo "--- /sys/bus/pci/devices 里有没有 0000:0b ---"
ls /sys/bus/pci/devices/ 2>/dev/null | grep -i "0b:" || echo "  没有 0000:0b:* 设备"
echo "--- 全部设备数 ---"
ls /sys/bus/pci/devices/ 2>/dev/null | wc -l
echo "--- 列出前 30 个 ---"
ls /sys/bus/pci/devices/ 2>/dev/null | head -30

echo
echo "########## 3. 直接问 sysfs 要 0b:00.0 的信息 ##########"
for f in vendor device class; do
  printf "  0b:00.0/%s = " $f
  cat /sys/bus/pci/devices/0000:0b:00.0/$f 2>&1
done

echo
echo "########## 4. dmesg 最近的 PCIe / 驱动 记录 ##########"
echo "--- 全部 dmesg 行数 ---"
dmesg 2>/dev/null | wc -l
echo "--- 含 pci/PCI 的最后 20 行 ---"
dmesg -T 2>/dev/null | grep -iE "pci" | tail -20
echo "--- 含 ascend/davinci/drv 的 ---"
dmesg -T 2>/dev/null | grep -iE "ascend|davinci|drv_|devdrv|devmm" | tail -20
echo "--- 最后 25 行（任意）---"
dmesg -T 2>/dev/null | tail -25

echo
echo "########## 5. 内核模块现状 ##########"
lsmod 2>/dev/null | head -20
echo "--- 模块总数 ---"
lsmod 2>/dev/null | wc -l

echo
echo "########## 6. 驱动安装包内容 ##########"
ls -la /usr/local/Ascend/driver/ 2>/dev/null | head -20
echo "--- ko 文件 ---"
find /usr/local/Ascend/driver -name "*.ko" 2>/dev/null | head -25
echo "--- ko 总数 ---"
find /usr/local/Ascend/driver -name "*.ko" 2>/dev/null | wc -l

echo
echo "########## 7. host_sys_init 服务状态 ##########"
systemctl status host_sys_init --no-pager 2>&1 | head -12
echo "--- 脚本内容 ---"
cat /etc/init.d/host_sys_init 2>/dev/null | head -30

echo
echo "########## 8. 设备节点现状（完整）##########"
ls -la /dev/ 2>/dev/null | grep -iE "davinci|devmm|hisi|hdc|svm" 

echo
echo "########## 9. 是否有 dpkg 记录的驱动包 ##########"
dpkg -l 2>/dev/null | grep -iE "ascend|npu|davinci" | head -10
