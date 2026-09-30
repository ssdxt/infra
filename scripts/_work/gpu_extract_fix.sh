#!/bin/bash
set -u
RPM=/root/JM9230/mwv207-dev-1.4.4-release.ky3.aarch64.rpm
EX=/tmp/mwv207-extract

echo "########## 1. 确认 rpm2cpio / cpio 工具 ##########"
which rpm2cpio cpio 2>&1

echo
echo "########## 2. 解包 rpm 到临时目录 ##########"
rm -rf $EX && mkdir -p $EX
cd $EX || exit 1
rpm2cpio "$RPM" | cpio -idm 2>&1 | tail -5
echo "  --- 解包结果 ---"
find $EX -type f 2>/dev/null | head -30
echo "  文件总数: $(find $EX -type f 2>/dev/null | wc -l)"

echo
echo "########## 3. 核对解包出的 mwv207 库 ##########"
ls -la $EX/usr/lib64/mwv207/ 2>&1
echo "  库文件数: $(ls $EX/usr/lib64/mwv207/ 2>/dev/null | wc -l)"

echo
echo "########## 4. 复制到 /usr/lib64/mwv207/ ##########"
mkdir -p /usr/lib64/mwv207
cp -avf $EX/usr/lib64/mwv207/. /usr/lib64/mwv207/ 2>&1 | tail -20
echo "  --- 复制后 ---"
ls -la /usr/lib64/mwv207/ 2>&1

echo
echo "########## 5. 复制其余文件（如有）##########"
if [ -d $EX/usr/lib64/dri ]; then
  cp -avf $EX/usr/lib64/dri/. /usr/lib64/dri/ 2>&1 | tail -5
fi
if [ -f $EX/usr/lib64/libdrm_jmgpu.so.1.0.0 ]; then
  cp -avf $EX/usr/lib64/libdrm_jmgpu.so.1.0.0 /usr/lib64/ 2>&1 | tail -3
fi

echo
echo "########## 6. 查看关键库的 SONAME（决定软链接）##########"
for f in /usr/lib64/mwv207/libGLX_mwv207.so.1.2.0 /usr/lib64/mwv207/libEGL_mwv207.so.1.5.0 /usr/lib64/mwv207/libJMC.so; do
  [ -e "$f" ] || { echo "  $f 不存在"; continue; }
  echo "--- $(basename $f) ---"
  readelf -d "$f" 2>/dev/null | grep -iE "SONAME"
done

echo
echo "########## 7. ldconfig 并把 mwv207 加入搜索路径 ##########"
echo "/usr/lib64/mwv207" > /etc/ld.so.conf.d/mwv207-aarch64.conf
ldconfig 2>&1 | head -3
echo "--- ldconfig 缓存 ---"
ldconfig -p 2>/dev/null | grep -iE "mwv207|JMC"

echo
echo "########## 8. 验证 jmgpu_dri.so 依赖 ##########"
ldd /usr/lib64/dri/jmgpu_dri.so 2>&1 | grep -iE "not found|GLX_mwv|JMC"
echo "  not found 计数: $(ldd /usr/lib64/dri/jmgpu_dri.so 2>&1 | grep -c 'not found')"

echo
echo "########## 9. 若 libGLX_mwv207.so.0 仍缺，手工补软链接 ##########"
if [ ! -e /usr/lib64/mwv207/libGLX_mwv207.so.0 ] && [ -e /usr/lib64/mwv207/libGLX_mwv207.so.1.2.0 ]; then
  echo "  创建 libGLX_mwv207.so.0 -> libGLX_mwv207.so.1.2.0"
  ln -sf libGLX_mwv207.so.1.2.0 /usr/lib64/mwv207/libGLX_mwv207.so.0
fi
if [ ! -e /usr/lib64/mwv207/libEGL_mwv207.so.0 ] && [ -e /usr/lib64/mwv207/libEGL_mwv207.so.1.5.0 ]; then
  ln -sf libEGL_mwv207.so.1.5.0 /usr/lib64/mwv207/libEGL_mwv207.so.0
fi
ldconfig
echo "--- 补链接后 mwv207 目录 ---"
ls -la /usr/lib64/mwv207/ 2>&1 | head -25
echo "--- 依赖复核 ---"
ldd /usr/lib64/dri/jmgpu_dri.so 2>&1 | grep -iE "not found|GLX_mwv|JMC"
echo "  not found 计数: $(ldd /usr/lib64/dri/jmgpu_dri.so 2>&1 | grep -c 'not found')"
