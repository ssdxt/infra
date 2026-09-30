#!/bin/bash
set -u
RPM=/root/JM9230/mwv207-dev-1.4.4-release.ky3.aarch64.rpm
TS=$(date +%Y%m%d-%H%M%S)

echo "########## 0. 修复前基线 ##########"
echo "--- jmgpu_dri.so 缺失依赖数 ---"
ldd /usr/lib64/dri/jmgpu_dri.so 2>/dev/null | grep -c "not found"
echo "--- /usr/lib64/mwv207 是否存在 ---"
ls -d /usr/lib64/mwv207 2>&1
echo "--- rpm 校验 ---"
rpm -V mwv207-dev 2>&1 | wc -l | sed 's/^/  missing 条目数: /'
echo "--- 备份 rpm 数据库中的包列表 ---"
rpm -qa | grep -i mwv > /root/mwv-pkgs-before-$TS.txt 2>&1
echo "  已存: /root/mwv-pkgs-before-$TS.txt"
echo "--- 备份 ld.so.conf.d ---"
cp -a /etc/ld.so.conf.d /root/ld.so.conf.d.bak-$TS 2>/dev/null
echo "  已存: /root/ld.so.conf.d.bak-$TS"

echo
echo "########## 1. 强制重装 mwv207-dev（恢复 15 个缺失库）##########"
if [ -f "$RPM" ]; then
  rpm -Uvh --force --replacepkgs "$RPM" 2>&1 | tail -10
  echo "  rpm 退出码: $?"
else
  echo "  !! 安装包不存在: $RPM"
  exit 1
fi

echo
echo "########## 2. 校验恢复结果 ##########"
echo "--- rpm -V（应无输出）---"
rpm -V mwv207-dev 2>&1 | head -20
echo "--- /usr/lib64/mwv207/ 内容 ---"
ls -la /usr/lib64/mwv207/ 2>&1
echo "--- 关键库是否到位 ---"
for f in libGLX_mwv207.so.1.2.0 libJMC.so libEGL_mwv207.so.1.5.0 libgbm.so.1.0.0; do
  printf "  %-32s " "$f"
  [ -e "/usr/lib64/mwv207/$f" ] && echo "OK" || echo "仍缺失"
done

echo
echo "########## 3. 查看库的 SONAME（决定要不要手工建软链接）##########"
for f in /usr/lib64/mwv207/libGLX_mwv207.so.1.2.0 /usr/lib64/mwv207/libEGL_mwv207.so.1.5.0 /usr/lib64/mwv207/libJMC.so; do
  [ -e "$f" ] || continue
  echo "--- $(basename $f) ---"
  readelf -d "$f" 2>/dev/null | grep -iE "SONAME"
done

echo
echo "########## 4. 把 /usr/lib64/mwv207 加入 ld 搜索路径 ##########"
echo "/usr/lib64/mwv207" > /etc/ld.so.conf.d/mwv207-aarch64.conf
cat /etc/ld.so.conf.d/mwv207-aarch64.conf
ldconfig 2>&1 | head -5
echo "--- ldconfig 缓存里的 mwv207 ---"
ldconfig -p 2>/dev/null | grep -iE "mwv207|JMC"

echo
echo "########## 5. 验证 jmgpu_dri.so 依赖是否补齐 ##########"
echo "--- ldd ---"
ldd /usr/lib64/dri/jmgpu_dri.so 2>&1 | grep -iE "not found|GLX|JMC|drm_jmgpu"
echo "--- not found 计数（应为 0）---"
ldd /usr/lib64/dri/jmgpu_dri.so 2>&1 | grep -c "not found"

echo
echo "########## 6. 现在测 glxinfo（Xorg 还在跑旧状态，可能仍失败）##########"
DISPLAY=:0 glxinfo -B 2>&1 | head -14
