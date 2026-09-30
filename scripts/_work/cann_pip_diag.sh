#!/bin/bash
echo "########## 1. sudo 环境下的 PATH（关键）##########"
echo "--- 当前 shell 的 PATH ---"
echo "  $PATH"
echo "--- sudo 下的 PATH ---"
sudo env 2>/dev/null | grep -i "^PATH=" | sed 's/^/  /'
echo "--- sudoers 里的 secure_path ---"
grep -nE "secure_path|env_reset|env_keep" /etc/sudoers 2>/dev/null
ls /etc/sudoers.d/ 2>/dev/null
for f in /etc/sudoers.d/*; do
  [ -f "$f" ] && echo "--- $f ---" && grep -nE "secure_path|PATH" "$f" 2>/dev/null
done

echo
echo "########## 2. 各类 python / pip 的位置 ##########"
echo "--- 当前环境 ---"
for c in python python3 pip pip3; do printf "  %-8s " $c; which $c 2>/dev/null || echo "(无)"; done
echo "--- sudo 环境下 ---"
for c in python python3 pip pip3; do printf "  %-8s " $c; sudo which $c 2>/dev/null || echo "(无)"; done
echo "--- 系统级目录里有没有 ---"
ls -la /usr/bin/python3 /usr/bin/pip3 /usr/local/bin/python3 /usr/local/bin/pip3 2>&1

echo
echo "########## 3. anaconda 里的 python/pip ##########"
ls -la /root/anaconda3/bin/python3 /root/anaconda3/bin/pip3 2>&1
/root/anaconda3/bin/python3 --version 2>&1
/root/anaconda3/bin/pip3 --version 2>&1

echo
echo "########## 4. CANN toolkit 安装日志（失败详情）##########"
tail -50 /var/log/ascend_seclog/ascend_toolkit_install.log 2>/dev/null

echo
echo "########## 5. 临时解压目录是否还在 ##########"
ls -d /root/selfgz* 2>/dev/null || echo "  已清理"
echo "--- 找 compiler_custom_install.sh ---"
find /root /tmp -name "compiler_custom_install.sh" 2>/dev/null | head -3

echo
echo "########## 6. 残留的 CANN 安装 ##########"
ls -la /usr/local/Ascend/ 2>/dev/null
echo "--- runtime 是否装上了 ---"
ls -d /usr/local/Ascend/ascend-toolkit/*/ 2>/dev/null
cat /usr/local/Ascend/ascend-toolkit/latest/version.cfg 2>/dev/null | head -5

echo
echo "########## 7. 确认 sudo 会丢 PATH 的复现 ##########"
echo -n "  sudo bash -c 'echo \$PATH' -> "
sudo bash -c 'echo $PATH'
echo -n "  sudo bash -c 'command -v pip3' -> "
sudo bash -c 'command -v pip3 || echo NOT_FOUND'
