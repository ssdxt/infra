#!/bin/bash
echo "########## 1. apt 源是否可用（决定能否装 python3-pip）##########"
timeout 60 apt-get update 2>&1 | tail -8
echo "--- 退出码: $? ---"
echo "--- 源列表 ---"
grep -rhvE "^\s*#|^\s*$" /etc/apt/sources.list /etc/apt/sources.list.d/*.list 2>/dev/null | head -10

echo
echo "########## 2. 源里有没有 python3-pip ##########"
apt-cache policy python3-pip 2>&1 | head -10

echo
echo "########## 3. 残留的卸载脚本 ##########"
ls -la /usr/local/Ascend/ascend-toolkit/8.1.RC1/cann_uninstall.sh 2>&1
echo "--- 脚本前 30 行 ---"
head -30 /usr/local/Ascend/ascend-toolkit/8.1.RC1/cann_uninstall.sh 2>/dev/null
echo "--- 顶层还有哪些卸载相关 ---"
find /usr/local/Ascend -maxdepth 3 -name "*uninstall*" 2>/dev/null

echo
echo "########## 4. toolkit 包支持的卸载参数 ##########"
cd /deploy/driver/Ascend
./Ascend-cann-toolkit_8.1.RC1_linux-aarch64.run --help 2>&1 | grep -iE "uninstall|install|quiet" | head -10

echo
echo "########## 5. 当前 pip3 候选（用于方案对比）##########"
echo "--- 系统 python3.8 ---"
/usr/bin/python3 -c "import sys; print('  ', sys.executable)" 2>&1
/usr/bin/python3 -m ensurepip --version 2>&1 | head -3
echo "--- anaconda ---"
/root/anaconda3/bin/pip3 --version 2>&1
echo "--- /usr/local/bin 可写? ---"
ls -ld /usr/local/bin

echo
echo "########## 6. 网络连通性（备选方案需要）##########"
for u in https://mirrors.aliyun.com https://pypi.tuna.tsinghua.edu.cn; do
  printf "  %-40s " $u
  curl -sI -m 8 "$u" -o /dev/null -w "%{http_code}\n" 2>/dev/null || echo "失败"
done
