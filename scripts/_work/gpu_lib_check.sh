#!/bin/bash
echo "########## 1. /usr/lib64/mwv207/ 完整内容（含软链接）##########"
ls -la /usr/lib64/mwv207/ 2>&1

echo
echo "########## 2. jmgpu_dri.so 到底要什么 SONAME ##########"
echo "--- NEEDED 条目 ---"
readelf -d /usr/lib64/dri/jmgpu_dri.so 2>/dev/null | grep -iE "NEEDED|SONAME|RPATH|RUNPATH"
echo "--- libEGL_mwv207 的 SONAME ---"
readelf -d /usr/lib64/mwv207/libEGL_mwv207.so.1.5.0 2>/dev/null | grep -iE "SONAME"
echo "--- libGLX_mwv207 的 SONAME ---"
readelf -d /usr/lib64/mwv207/libGLX_mwv207.so.1.2.0 2>/dev/null | grep -iE "SONAME"

echo
echo "########## 3. ld 搜索路径里有没有 mwv207 ##########"
ldconfig -p 2>/dev/null | grep -iE "mwv|JMC|jmc"
echo "--- 所有 ld.so.conf.d 内容里有 mwv 的 ---"
grep -rl "mwv" /etc/ld.so.conf.d/ 2>/dev/null
echo "--- 当前 ld 有效路径 ---"
ldconfig -v -N 2>/dev/null | grep -E "^/" | head -20

echo
echo "########## 4. switch-gl.sh 是什么工具 ##########"
cat /opt/mwv207/usr/sbin/switch-gl.sh 2>/dev/null
echo "--- 是否可执行 ---"
ls -la /opt/mwv207/usr/sbin/switch-gl.sh /opt/mwv207/usr/sbin/delete-shader-cache 2>&1

echo
echo "########## 5. 手动加路径测试（临时，不改配置）##########"
echo "--- 临时 LD_LIBRARY_PATH 测试 jmgpu_dri.so 依赖 ---"
LD_LIBRARY_PATH=/usr/lib64/mwv207 ldd /usr/lib64/dri/jmgpu_dri.so 2>&1 | grep -iE "not found|GLX|JMC|drm_jmgpu"
echo "--- 临时 LD_LIBRARY_PATH 测 glxinfo ---"
DISPLAY=:0 LD_LIBRARY_PATH=/usr/lib64/mwv207 glxinfo -B 2>&1 | head -18

echo
echo "########## 6. GLVND vendor 配置现状 ##########"
echo "--- __GLX_VENDOR_LIBRARY_NAME ---"
echo "  当前值: ${__GLX_VENDOR_LIBRARY_NAME:-<未设置>}"
echo "--- /usr/share/glvnd/egl_vendor.d/ ---"
ls -la /usr/share/glvnd/egl_vendor.d/ 2>/dev/null
for f in /usr/share/glvnd/egl_vendor.d/*.json; do [ -f "$f" ] && echo "--- $f ---" && cat "$f"; done
echo "--- /dev/jmgpu 是否存在（脚本里判断这个）---"
ls -la /dev/jmgpu 2>&1

echo
echo "########## 7. 现有 GL 库全景 ##########"
echo "--- /usr/lib64 下的 libGL* libEGL* ---"
ls -la /usr/lib64/libGL*.so* /usr/lib64/libEGL*.so* 2>/dev/null | head -20
echo "--- /usr/lib64/mwv207 下全部 ---"
ls /usr/lib64/mwv207/ 2>/dev/null | wc -l
