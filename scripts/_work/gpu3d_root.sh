#!/bin/bash
echo "########## 1. jmgpu_dri.so 的依赖是否齐全（关键）##########"
echo "--- file ---"
file /usr/lib64/dri/jmgpu_dri.so 2>&1
echo "--- ldd ---"
ldd /usr/lib64/dri/jmgpu_dri.so 2>&1 | head -30
echo "--- ldd 里 not found 的 ---"
ldd /usr/lib64/dri/jmgpu_dri.so 2>&1 | grep -i "not found" || echo "  依赖齐全"

echo
echo "########## 2. /usr/lib64/dri/ 完整内容 ##########"
ls -la /usr/lib64/dri/ 2>&1

echo
echo "########## 3. Mesa 的驱动搜索路径 ##########"
echo "  LIBGL_DRIVERS_PATH=${LIBGL_DRIVERS_PATH:-<空>}"
echo "  LIBGL_DEBUG=${LIBGL_DEBUG:-<空>}"
echo "--- libGL.so 里编译进去的路径 ---"
for f in /usr/lib64/libGL.so.1 /usr/lib64/libGLX_mesa.so.0; do
  [ -f "$f" ] && echo "--- $f ---" && strings "$f" 2>/dev/null | grep -oE "/usr/lib[0-9a-z_/-]*dri" | sort -u | head -5
done
echo "--- ld.so.conf ---"
cat /etc/ld.so.conf 2>/dev/null
ls /etc/ld.so.conf.d/ 2>/dev/null
for f in /etc/ld.so.conf.d/*.conf; do [ -f "$f" ] && echo "--- $f ---" && cat "$f"; done

echo
echo "########## 4. libdrm_jmgpu 与相关库 ##########"
ls -la /usr/lib64/libdrm* 2>/dev/null
echo "--- ldconfig 缓存里的 jmgpu/jm ---"
ldconfig -p 2>/dev/null | grep -iE "jmgpu|jingjia|drm_jm"

echo
echo "########## 5. 用 LIBGL_DEBUG=verbose 看详细失败原因 ##########"
DISPLAY=:0 LIBGL_DEBUG=verbose glxinfo -B 2>&1 | head -35

echo
echo "########## 6. Mesa 是否认识这块卡的 PCI ID ##########"
echo "--- jmgpu_dri.so 里的 PCI ID 字符串 ---"
strings /usr/lib64/dri/jmgpu_dri.so 2>/dev/null | grep -iE "0731|9230|jmgpu|mwv207" | head -10
echo "--- Mesa 主库里的 jmgpu 支持 ---"
for f in /usr/lib64/libGLX_mesa.so.0 /usr/lib64/libgallium*.so* /usr/lib64/dri/swrast_dri.so; do
  [ -f "$f" ] && echo "  $f: $(strings "$f" 2>/dev/null | grep -ciE 'jmgpu|jm9230') 处匹配"
done

echo
echo "########## 7. 直接手动指定驱动路径测试 ##########"
DISPLAY=:0 LIBGL_DRIVERS_PATH=/usr/lib64/dri LIBGL_DEBUG=verbose glxinfo -B 2>&1 | grep -iE "error|renderer|Accelerated" | head -12

echo
echo "########## 8. jmgpu_dri.so 的 ELF 头 ##########"
readelf -h /usr/lib64/dri/jmgpu_dri.so 2>/dev/null | head -12
echo "--- 缺失的符号（如果有）---"
ldd -r /usr/lib64/dri/jmgpu_dri.so 2>&1 | grep -iE "undefined|not found" | head -10 || echo "  无未定义符号问题"

echo
echo "########## 9. Xorg 的 GLX 扩展 ##########"
ls -la /usr/lib64/xorg/modules/extensions/ 2>/dev/null
grep -iE "glx|GLX" /var/log/Xorg.0.log 2>/dev/null | head -15

echo
echo "########## 10. 驱动包安装情况 ##########"
dpkg -l 2>/dev/null | grep -iE "mwv207|jmgpu|jingjia|jm9" 
dpkg -S /usr/lib64/dri/jmgpu_dri.so 2>&1 | head -3
