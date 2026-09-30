#!/bin/bash
set -u
echo "########## 1. 重启前的 glxinfo（预期仍是 llvmpipe）##########"
DISPLAY=:0 glxinfo -B 2>&1 | grep -iE "renderer|Accelerated|Vendor|Device" | head -6

echo
echo "########## 2. 确认库状态再重启 ##########"
ldd /usr/lib64/dri/jmgpu_dri.so 2>&1 | grep -c "not found" | sed 's/^/  jmgpu_dri.so not found 数: /'
ls /usr/lib64/mwv207/ 2>/dev/null | wc -l | sed 's/^/  mwv207 目录库数: /'
cat /etc/ld.so.conf.d/mwv207-aarch64.conf

echo
echo "########## 3. 记录 lightdm 当前状态 ##########"
systemctl is-active lightdm 2>&1 | sed 's/^/  lightdm: /'
ps -ef 2>/dev/null | grep -cE "[X]org" | sed 's/^/  Xorg 进程数: /'

echo
echo "########## 4. 重启 lightdm ##########"
systemctl restart lightdm 2>&1
echo "  重启命令已发出，等待 X 起来..."
for i in $(seq 1 12); do
  sleep 5
  X=$(ps -ef 2>/dev/null | grep -cE "[X]org")
  L=$(systemctl is-active lightdm 2>&1)
  echo "  [$((i*5))s] lightdm=$L  Xorg进程=$X"
  if [ "$X" -ge 1 ]; then break; fi
done

echo
echo "########## 5. 重启后的 glxinfo（关键验证）##########"
DISPLAY=:0 glxinfo -B 2>&1 | head -20

echo
echo "########## 6. 关键行提取 ##########"
DISPLAY=:0 glxinfo 2>/dev/null | grep -iE "OpenGL renderer|OpenGL vendor|OpenGL version|direct rendering" | head -6

echo
echo "########## 7. Xorg 日志里 AIGLX 的结果 ##########"
grep -iE "AIGLX|jmgpu|swrast|GLX:|Initialized" /var/log/Xorg.0.log 2>/dev/null | tail -15

echo
echo "########## 8. 3D 利用率复核 ##########"
grep -iE "Utilize|Temperature" /proc/gpuinfo_0

echo
echo "########## 9. EGL 验证 ##########"
DISPLAY=:0 eglinfo 2>/dev/null | grep -iE "Vendor|Renderer|Version" | head -8
