#!/bin/bash
echo "########## 0. 这台机器是谁 ##########"
hostname
echo "uptime: $(uptime 2>&1)"
ip -4 addr show 2>/dev/null | grep -oP 'inet \K[\d.]+' | grep -v 127.0.0.1 | sed 's/^/  IP: /'
cat /etc/os-release 2>/dev/null | head -3
uname -r

echo
echo "########## 1. /proc/gpuinfo_0 原始内容 ##########"
ls -la /proc/gpuinfo* 2>&1
echo "--- cat /proc/gpuinfo_0 ---"
cat /proc/gpuinfo_0 2>&1
echo "--- exit code: $? ---"

echo
echo "########## 2. 所有 /proc 下 gpu 相关文件 ##########"
ls -la /proc/ 2>/dev/null | grep -iE "gpu|drm|video|graphics"
echo "--- 逐个尝试读取 ---"
for f in /proc/gpuinfo*; do
  [ -e "$f" ] || continue
  echo "--- $f ---"
  cat "$f" 2>&1 | head -30
done

echo
echo "########## 3. lspci 里的显示设备 ##########"
lspci -nn 2>/dev/null | grep -iE "vga|display|3d|graphics"
echo "--- 详细 ---"
lspci -v 2>/dev/null | grep -A5 -iE "VGA compatible|Display controller" | head -30

echo
echo "########## 4. 显卡驱动加载情况 ##########"
lsmod 2>/dev/null | grep -iE "amdgpu|radeon|drm|nouveau|i915|zxdrm|phytium" || echo "  无常见显卡驱动模块"
echo "--- 全部 drm 相关 ---"
lsmod 2>/dev/null | grep -i drm

echo
echo "########## 5. DRM 设备节点 ##########"
ls -la /dev/dri/ 2>&1
echo "--- sysfs drm ---"
ls /sys/class/drm/ 2>/dev/null

echo
echo "########## 6. dmesg 里的显卡初始化 ##########"
dmesg -T 2>/dev/null | grep -iE "amdgpu|radeon|drm|vga|framebuffer|efifb|simpledrm|gpu" | head -30

echo
echo "########## 7. 图形栈状态 ##########"
echo "  DISPLAY=${DISPLAY:-<空>}"
systemctl get-default 2>/dev/null
echo "  graphical.target: $(systemctl is-active graphical.target 2>&1)"
echo "--- 显示管理器 ---"
systemctl is-active lightdm gdm sddm 2>&1 | head -3
echo "--- X / Wayland 进程 ---"
ps -ef 2>/dev/null | grep -E "[X]org|[w]ayland|[l]ightdm|[g]dm" | head -5

echo
echo "########## 8. 显卡相关固件/驱动包 ##########"
ls /lib/firmware/amdgpu/ 2>/dev/null | head -10
dpkg -l 2>/dev/null | grep -iE "mesa|drm|amdgpu|radeon|xserver" | head -12
