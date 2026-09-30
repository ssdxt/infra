#!/bin/bash
echo "########## 1. modprobe 之后模块与设备的真实状态 ##########"
lsmod 2>/dev/null | grep -iE "drv_|ascend|davinci" | head -20
echo "  模块数: $(lsmod 2>/dev/null | grep -icE 'drv_|ascend')"
echo "--- /dev 下 NPU 节点 ---"
ls -la /dev/ 2>/dev/null | grep -iE "davinci|devmm|hisi|svm" | head -10

echo
echo "########## 2. modprobe 的 dmesg 记录（看驱动怎么说的）##########"
dmesg -T 2>/dev/null | tail -25

echo
echo "########## 3. Ascend 安全日志 / 安装日志 ##########"
ls -la /var/log/ascend_seclog/ 2>/dev/null | head -10
echo "--- 关键日志尾部 ---"
for f in /var/log/ascend_seclog/ascend_install.log /var/log/ascend_seclog/ascend_run_servers.log; do
  [ -f "$f" ] && echo "--- $f ---" && tail -15 "$f"
done

echo
echo "########## 4. 驱动版本信息（完整）##########"
cat /usr/local/Ascend/driver/version.info 2>/dev/null

echo
echo "########## 5. 模块文件位置 ##########"
KVER=$(uname -r)
echo "  内核: $KVER"
find /lib/modules/$KVER -iname "drv_*" -o -iname "*davinci*" -o -iname "*ascend*" 2>/dev/null | head -20
echo "  模块文件数: $(find /lib/modules/$KVER -iname 'drv_*.ko*' 2>/dev/null | wc -l)"
echo "--- modules.dep 里的 ascend 条目 ---"
grep -icE "drv_|ascend" /lib/modules/$KVER/modules.dep 2>/dev/null

echo
echo "########## 6. 是否装过 DKMS 驱动 ##########"
dkms status 2>/dev/null || echo "  无 dkms"
ls /var/lib/dkms/ 2>/dev/null | head -5

echo
echo "########## 7. PCIe 总线拓扑（0b 总线该在哪）##########"
echo "--- 00:00.0 下游总线范围 ---"
lspci -tv 2>/dev/null | head -25

echo
echo "########## 8. 是否有 PCIe 错误 / AER ##########"
dmesg -T 2>/dev/null | grep -iE "aer|pcie.*error|link down|link.*fail" | tail -10 || echo "  无 PCIe 错误记录"

echo
echo "########## 9. 本次启动 vs 上次启动（如果有记录）##########"
journalctl --list-boots --no-pager 2>/dev/null | tail -5
echo "--- 上次启动有没有 ascend 记录 ---"
journalctl -k -b -1 --no-pager 2>/dev/null | grep -icE "ascend|davinci|19e5" | sed 's/^/  匹配行数: /'
