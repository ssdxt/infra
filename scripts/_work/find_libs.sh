#!/bin/bash
echo "########## 1. 全盘搜索缺失的两个库 ##########"
echo "--- libGLX_mwv207 ---"
find / -xdev -name "libGLX_mwv207*" 2>/dev/null
find /usr /opt /lib /deploy /root -name "libGLX_mwv207*" 2>/dev/null | head -10
echo "--- libJMC ---"
find / -xdev -name "libJMC*" 2>/dev/null
find /usr /opt /lib /deploy /root -name "libJMC*" 2>/dev/null | head -10
echo "--- 也搜 drv_video 用的同名库 ---"
find / -xdev -name "*mwv207*" 2>/dev/null | head -20

echo
echo "########## 2. ldconfig 缓存里有没有 ##########"
ldconfig -p 2>/dev/null | grep -iE "mwv207|JMC|jmgpu"

echo
echo "########## 3. 景嘉微驱动包在系统里怎么装的 ##########"
dpkg -l 2>/dev/null | grep -iE "mwv207|jmgpu|jingjia|jm9|jjw"
echo "--- dpkg -S 反查 ---"
dpkg -S /usr/lib64/dri/jmgpu_dri.so 2>&1 | head -3
dpkg -S /usr/lib64/libdrm_jmgpu.so.1.0.0 2>&1 | head -3
echo "--- /usr/lib64/xorg/modules 结构 ---"
ls -la /usr/lib64/xorg/modules/ 2>/dev/null
echo "--- extensions ---"
ls -la /usr/lib64/xorg/modules/extensions/ 2>/dev/null
echo "--- drivers ---"
ls -la /usr/lib64/xorg/modules/drivers/ 2>/dev/null | grep -iE "mwv|jmgpu|modesetting"

echo
echo "########## 4. 驱动源码目录里有没有预编译好的库 ##########"
ls -la /usr/src/mwv207-1.4.4/ 2>/dev/null | head -30
echo "--- 该目录下的 .so ---"
find /usr/src/mwv207-1.4.4 -name "*.so*" 2>/dev/null | head -20

echo
echo "########## 5. 安装介质里有没有（tar/deb/rpm）##########"
find / -xdev -maxdepth 4 \( -iname "*mwv207*" -o -iname "*jmgpu*" -o -iname "*jingjia*" \) \( -name "*.deb" -o -name "*.rpm" -o -name "*.tar*" -o -name "*.run" \) 2>/dev/null | head -10
ls -la /deploy/ 2>/dev/null | head -15

echo
echo "########## 6. 其它景嘉微系列（ljm）是否正常（对照）##########"
echo "--- ljm_dri.so 的依赖 ---"
ldd /usr/lib64/dri/ljm_dri.so 2>&1 | grep -iE "not found|GLX|JMC|drm_ljm|drm_jmgpu"
echo "--- ljm 相关库 ---"
ls -la /usr/lib64/ | grep -iE "ljm|GLX"

echo
echo "########## 7. Xorg 的 GLX 模块（libGLX_mwv207 应该由它提供）##########"
grep -iE "libGLX|glx" /var/log/Xorg.0.log 2>/dev/null | head -20

echo
echo "########## 8. 整机文件系统里所有 GLX 相关库 ##########"
find / -xdev -name "libGLX*" 2>/dev/null | head -20

echo
echo "########## 9. 驱动安装日志 ##########"
ls -la /var/log/ 2>/dev/null | grep -iE "mwv|jmgpu|jingjia|gpu"
ls /usr/src/ 2>/dev/null
