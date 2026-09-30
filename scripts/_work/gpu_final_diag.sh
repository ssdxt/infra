#!/bin/bash
echo "########## 1. rpm 校验 mwv207-dev（看哪些文件缺失）##########"
rpm -V mwv207-dev 2>&1 | head -40
echo "--- 退出码: $? ---"
echo "--- 缺失文件的分类统计 ---"
rpm -V mwv207-dev 2>&1 | awk '{print $1}' | sort | uniq -c | sort -rn | head

echo
echo "########## 2. 包声称提供 vs 磁盘实际 ##########"
echo "--- 包里的文件清单 ---"
rpm -ql mwv207-dev 2>/dev/null | grep -E "\.so" | head -30
echo "--- 逐一检查存在性 ---"
rpm -ql mwv207-dev 2>/dev/null | while read f; do
  [ -e "$f" ] || echo "  缺失: $f"
done | head -30

echo
echo "########## 3. 相关目录是否存在 ##########"
for d in /usr/lib64/mwv207 /usr/lib64/mwv206 /opt/mwv207 /usr/lib64/mesa /usr/lib/mwv207; do
  printf "  %-28s " "$d"
  if [ -d "$d" ]; then echo "存在 ($(ls $d 2>/dev/null | wc -l) 项)"; else echo "不存在"; fi
done

echo
echo "########## 4. 系统里所有 mwv/景嘉微 的 .so ##########"
find / -xdev -name "*mwv*" 2>/dev/null | head -20
echo "--- /usr/lib64 下 ---"
ls /usr/lib64/ 2>/dev/null | grep -iE "mwv|jmc"

echo
echo "########## 5. /dev/cur_gl 是否存在（switch-gl.sh 的关键判断）##########"
ls -la /dev/cur_gl 2>&1
echo "--- /dev/jmgpu ---"
ls -la /dev/jmgpu 2>&1
echo "--- /dev 下所有 gl 相关 ---"
ls -la /dev/ 2>/dev/null | grep -iE "gl|gpu"

echo
echo "########## 6. switch-gl.sh 的权限与依赖 ##########"
ls -la /opt/mwv207/usr/sbin/switch-gl.sh 2>&1
head -1 /opt/mwv207/usr/sbin/switch-gl.sh 2>/dev/null
echo "--- 它依赖 dpkg（本机是 rpm 系，可能无法运行）---"
which dpkg rpm gcc 2>/dev/null

echo
echo "########## 7. 安装介质里的 rpm 是否完整 ##########"
for f in /root/JM9230/*.rpm; do
  echo "--- $(basename $f) ---"
  rpm -qp --qf '  包名: %{NAME}  版本: %{VERSION}-%{RELEASE}  架构: %{ARCH}\n' "$f" 2>&1
  echo "  提供关键库: $(rpm -qlp "$f" 2>/dev/null | grep -cE 'libGLX_mwv207|libJMC')"
done

echo
echo "########## 8. 当前 GL 实现归属 ##########"
echo "--- libGL.so.1 指向谁 ---"
ls -la /usr/lib64/libGL.so.1 /usr/lib64/libGL.so 2>&1
echo "--- libEGL.so.1 指向谁 ---"
ls -la /usr/lib64/libEGL.so.1 2>&1
echo "--- glvnd 配置 ---"
ls -la /usr/share/glvnd/egl_vendor.d/ 2>/dev/null

echo
echo "########## 9. rpm 数据库一致性 ##########"
rpm -qa 2>/dev/null | grep -iE "mwv207|mwv206" 
echo "--- 有没有 .rpmsave/.rpmnew 残留 ---"
find / -xdev -name "*.rpmsave" -o -name "*.rpmnew" 2>/dev/null | head -10
