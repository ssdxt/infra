#!/bin/bash
echo "########## 1. 安装介质目录 ##########"
echo "--- /root/JM9230 ---"
ls -laR /root/JM9230/ 2>/dev/null | head -40
echo "--- /deploy/driver ---"
ls -laR /deploy/driver/ 2>/dev/null | head -40
echo "--- /deploy/tar ---"
ls -la /deploy/tar/ 2>/dev/null

echo
echo "########## 2. GLVND 配置脚本说要库在哪 ##########"
for f in /etc/profile.d/mwv207_glvnd.sh /etc/X11/xinit/xinitrc.d/50-mwv207-glvnd.sh; do
  echo "--- $f ---"
  cat "$f" 2>/dev/null
done
echo "--- egl_vendor ---"
cat /usr/share/glvnd/egl_vendor.d/10_mwv207.json 2>/dev/null
echo "--- xorg conf ---"
cat /usr/share/X11/xorg.conf.d/10-mwv207.conf 2>/dev/null

echo
echo "########## 3. rpm 数据库里景嘉微相关包 ##########"
rpm -qa 2>/dev/null | grep -iE "mwv|jmgpu|jingjia|jm9|jjw|ljm"
echo "--- 总数 ---"
rpm -qa 2>/dev/null | wc -l

echo
echo "########## 4. 已安装的 mwv207 包提供哪些文件 ##########"
for p in $(rpm -qa 2>/dev/null | grep -iE "mwv|jmgpu"); do
  echo "===== $p ====="
  rpm -ql "$p" 2>/dev/null | head -25
done

echo
echo "########## 5. 每个 rpm 安装包里的文件清单（找 GLX / JMC）##########"
for f in /root/JM9230/*.rpm; do
  [ -f "$f" ] || continue
  echo "===== $(basename $f) ====="
  rpm -qlp "$f" 2>/dev/null | head -30
  echo "  --- 含 GLX/JMC 的 ---"
  rpm -qlp "$f" 2>/dev/null | grep -iE "GLX|JMC|\.so" | head -15
done

echo
echo "########## 6. 有没有别的目录存着完整驱动包 ##########"
find / -xdev -maxdepth 5 \( -iname "*mwv207*" -o -iname "*JM9230*" -o -iname "*jmgpu*" \) \( -name "*.rpm" -o -name "*.deb" -o -name "*.tar*" -o -name "*.run" -o -name "*.zip" \) 2>/dev/null | head -20

echo
echo "########## 7. 全系统搜 .so 里含 jmgpu/GLX_mwv 符号的 ##########"
echo "--- /usr/lib64 下所有可能相关的 .so ---"
ls /usr/lib64/ 2>/dev/null | grep -iE "jmgpu|jmc|mwv|jingjia"
echo "--- /usr/lib64/xorg/modules/extensions ---"
ls -la /usr/lib64/xorg/modules/extensions/
echo "--- libglx.so 是否引用 libGLX_mwv207 ---"
strings /usr/lib64/xorg/modules/extensions/libglx.so 2>/dev/null | grep -iE "mwv207|jmgpu" | head -5

echo
echo "########## 8. 历史：这些库曾经存在过吗 ##########"
find / -xdev -name "libGLX_mwv207*" -o -name "libJMC*" 2>/dev/null | head
echo "--- rpm 数据库里有没有文件记录指向它们 ---"
rpm -qf /usr/lib64/dri/jmgpu_dri.so 2>&1 | head -3
rpm -qf /usr/lib64/libdrm_jmgpu.so.1.0.0 2>&1 | head -3
