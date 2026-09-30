#!/bin/bash
echo "########## 1. 包管理器与系统 python ##########"
for c in apt apt-get yum dnf rpm dpkg; do printf "  %-8s " $c; which $c 2>/dev/null || echo "(无)"; done
echo "--- 系统 python3 ---"
/usr/bin/python3 --version 2>&1
echo "--- 系统 python3 有没有 pip 模块 ---"
/usr/bin/python3 -m pip --version 2>&1 | head -2
echo "--- 系统 python3 的 site-packages 里有没有 pip ---"
/usr/bin/python3 -c "import pip; print('pip ok', pip.__version__)" 2>&1 | head -2

echo
echo "########## 2. ascend-toolkit 残留状态 ##########"
echo "--- 目录结构 ---"
find /usr/local/Ascend/ascend-toolkit -maxdepth 2 2>/dev/null | head -20
echo "--- 大小 ---"
du -sh /usr/local/Ascend/ascend-toolkit 2>/dev/null
echo "--- version.cfg ---"
cat /usr/local/Ascend/ascend-toolkit/latest/version.cfg 2>/dev/null | head -5
echo "--- 是否有卸载脚本 ---"
ls -la /usr/local/Ascend/ascend-toolkit/*/script/uninstall.sh 2>/dev/null
ls -la /usr/local/Ascend/ascend-toolkit/latest/script/ 2>/dev/null | head -10

echo
echo "########## 3. CANN 各组件安装状态 ##########"
echo "--- /usr/local/Ascend 总览 ---"
ls -la /usr/local/Ascend/ 2>/dev/null
echo "--- 各组件版本 ---"
for d in ascend-toolkit nnrt nnal; do
  printf "  %-18s " "$d"
  if [ -d "/usr/local/Ascend/$d" ]; then
    echo "存在: $(ls /usr/local/Ascend/$d 2>/dev/null | tr '\n' ' ')"
  else
    echo "不存在"
  fi
done

echo
echo "########## 4. CANN 包的卸载方式 ##########"
ls -la /deploy/driver/Ascend/*.run 2>/dev/null
echo "--- toolkit 包内是否有卸载参数说明 ---"
strings /deploy/driver/Ascend/Ascend-cann-toolkit_8.1.RC1_linux-aarch64.run 2>/dev/null | grep -iE "^--uninstall|--install-path|--quiet" | head -5

echo
echo "########## 5. 环境变量与软链接 ##########"
ls -la /etc/profile.d/ 2>/dev/null | grep -i ascend
cat /etc/profile.d/ascend-toolkit.sh 2>/dev/null | head -10
echo "--- ld.so.conf.d 里的 ascend ---"
ls /etc/ld.so.conf.d/ 2>/dev/null | grep -i ascend
cat /etc/ld.so.conf.d/ascend*.conf 2>/dev/null

echo
echo "########## 6. 之前的 toolkit 安装日志开头（看它怎么调 pip3）##########"
head -40 /var/log/ascend_seclog/ascend_toolkit_install.log 2>/dev/null
