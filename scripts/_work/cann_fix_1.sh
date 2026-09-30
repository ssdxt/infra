#!/bin/bash
# CANN toolkit 安装失败修复 —— 阶段 1：补 pip3 + 完整卸载脚本审阅
set +e

echo "########## A. cann_uninstall.sh 全文 ##########"
cat /usr/local/Ascend/ascend-toolkit/8.1.RC1/cann_uninstall.sh

echo
echo "########## B. 各子组件是否带 uninstall.sh ##########"
for d in aarch64-linux compiler python; do
  p=/usr/local/Ascend/ascend-toolkit/8.1.RC1/$d
  printf "  %-16s " "$d"
  if [ -d "$p" ]; then
    if [ -f "$p/script/uninstall.sh" ]; then echo "有 script/uninstall.sh"
    elif [ -f "$p/uninstall.sh" ]; then echo "有 uninstall.sh"
    else echo "无卸载脚本 (子项: $(ls "$p" 2>/dev/null | head -6 | tr '\n' ' '))"; fi
  else echo "目录不存在"; fi
done

echo
echo "########## C. toolkit .run 的全部 --* 选项（找 uninstall）##########"
cd /deploy/driver/Ascend
./Ascend-cann-toolkit_8.1.RC1_linux-aarch64.run --help 2>&1 | grep -oE '^\s+--[a-z-]+' | sort -u

echo
echo "########## D. 安装 python3-pip（Kylin 官方源）##########"
apt-get install -y python3-pip 2>&1 | tail -15
echo "--- 退出码: ${PIPESTATUS[0]} ---"
echo "--- 结果 ---"
ls -l /usr/bin/pip3 /usr/bin/pip 2>&1
/usr/bin/pip3 --version 2>&1

echo
echo "########## E. 确认 secure_path 下可见 pip3 ##########"
sudo bash -c 'command -v pip3 || echo NOT_FOUND'
sudo bash -c 'pip3 --version' 2>&1
