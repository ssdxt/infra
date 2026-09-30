#!/bin/bash
echo "########## 1. 3D 渲染节点被谁占用 ##########"
ls -la /dev/dri/
echo "--- lsof renderD128 ---"
lsof /dev/dri/renderD128 2>/dev/null || echo "  lsof 无结果（或未安装）"
echo "--- fuser ---"
fuser -v /dev/dri/renderD128 2>&1 | head -10
echo "--- fuser card0 ---"
fuser -v /dev/dri/card0 2>&1 | head -10

echo
echo "########## 2. OpenGL 真实渲染器（关键：硬件还是软件）##########"
which glxinfo eglinfo es2_info 2>/dev/null
echo "--- DISPLAY=:0 glxinfo ---"
DISPLAY=:0 glxinfo -B 2>&1 | head -20
echo "--- glxinfo 关键行 ---"
DISPLAY=:0 glxinfo 2>/dev/null | grep -iE "OpenGL renderer|OpenGL version|OpenGL vendor|direct rendering" | head -10

echo
echo "########## 3. Xorg 用的什么驱动 ##########"
ls -la /var/log/Xorg.0.log 2>/dev/null
grep -iE "\(II\).*driver|jmgpu|modesetting|fbdev|vesa|Loading.*dri" /var/log/Xorg.0.log 2>/dev/null | head -25
echo "--- Xorg 配置片段 ---"
ls -la /etc/X11/xorg.conf /etc/X11/xorg.conf.d/ 2>/dev/null
for f in /etc/X11/xorg.conf /etc/X11/xorg.conf.d/*; do
  [ -f "$f" ] && echo "--- $f ---" && cat "$f"
done

echo
echo "########## 4. Mesa / DRI 驱动库 ##########"
ls /usr/lib/aarch64-linux-gnu/dri/ 2>/dev/null | head -20
echo "--- libGL ---"
ls -la /usr/lib/aarch64-linux-gnu/libGL* /usr/lib/aarch64-linux-gnu/libEGL* 2>/dev/null | head -10
echo "--- 景嘉微自己的 GL 库 ---"
find / -xdev -iname "*jmgpu*" -o -iname "*jmgl*" -o -iname "*jingjia*" 2>/dev/null | head -20
echo "--- mesa 包 ---"
dpkg -l 2>/dev/null | grep -iE "mesa|libgl|libegl" | head -12

echo
echo "########## 5. 当前有没有 3D 应用 ##########"
ps -ef 2>/dev/null | grep -iE "[g]lx|[3]d|[g]ame|[b]lender|[g]ears|[u]nity|[c]ompositor" | head -10
echo "--- 桌面环境与合成器 ---"
echo "  XDG_CURRENT_DESKTOP=$XDG_CURRENT_DESKTOP"
ps -ef 2>/dev/null | grep -iE "[m]arco|[c]ompton|[p]icom|[k]win|[m]utter|[g]nome-shell|[u]kui" | head -8

echo
echo "########## 6. 实时读 /proc/gpuinfo_0 的利用率（间隔采样）##########"
for i in 1 2 3; do
  echo "--- 采样 $i ---"
  grep -iE "Utilize|Temperature|Remain" /proc/gpuinfo_0
  sleep 2
done

echo
echo "########## 7. 驱动模块详情 ##########"
lsmod 2>/dev/null | grep -iE "jmgpu|jm" 
modinfo jmgpu 2>/dev/null | head -12
echo "--- 模块参数 ---"
ls /sys/module/jmgpu/parameters/ 2>/dev/null

echo
echo "########## 8. DRM 版本与能力 ##########"
cat /sys/class/drm/version 2>/dev/null
cat /sys/class/drm/card0/device/uevent 2>/dev/null | head -10
echo "--- renderD128 的 sysfs ---"
ls /sys/class/drm/renderD128/device/ 2>/dev/null | head -10
