#!/bin/bash
echo "########## 1. 架构与系统 ##########"
uname -m
uname -r
cat /etc/os-release 2>/dev/null | head -4
echo "uptime: $(uptime 2>&1)"

echo
echo "########## 2. 包管理器 ##########"
which apt apt-get yum dnf rpm dpkg 2>/dev/null
echo "--- dpkg 架构 ---"
dpkg --print-architecture 2>/dev/null

echo
echo "########## 3. APT 软件源 ##########"
echo "--- /etc/apt/sources.list ---"
cat /etc/apt/sources.list 2>/dev/null | grep -vE "^\s*#|^\s*$" | head -20
echo "--- sources.list.d ---"
ls -la /etc/apt/sources.list.d/ 2>/dev/null
for f in /etc/apt/sources.list.d/*; do
  [ -f "$f" ] && echo "--- $f ---" && grep -vE "^\s*#|^\s*$" "$f" | head -10
done

echo
echo "########## 4. 源里有没有 chromium / chrome ##########"
apt-cache search chromium 2>/dev/null | head -10
echo "--- 精确查 ---"
apt-cache policy chromium chromium-browser google-chrome-stable 2>/dev/null | head -20

echo
echo "########## 5. 已安装的浏览器 ##########"
which chromium chromium-browser google-chrome firefox 2>/dev/null
dpkg -l 2>/dev/null | grep -iE "chrom|firefox" | head -10

echo
echo "########## 6. 网络连通性（能否访问外网源）##########"
for u in https://mirrors.aliyun.com https://deb.debian.org https://dl.google.com; do
  printf "  %-32s " "$u"
  curl -sI -m 6 "$u" -o /dev/null -w "%{http_code}\n" 2>/dev/null || echo "失败"
done

echo
echo "########## 7. 是否已有 chrome 安装包 ##########"
ls -la /root/*.deb /tmp/*.deb /deploy/*.deb 2>/dev/null | head -10
find /root /tmp /deploy -maxdepth 3 -iname "*chrome*" 2>/dev/null | head -10

echo
echo "########## 8. 桌面环境（有没有图形界面）##########"
echo "DISPLAY=$DISPLAY"
systemctl get-default 2>/dev/null
systemctl is-active graphical.target 2>/dev/null | sed 's/^/  graphical.target: /'
ls /usr/share/xsessions/ 2>/dev/null
