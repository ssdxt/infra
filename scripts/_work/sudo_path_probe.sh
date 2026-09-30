#!/bin/bash
echo "=== 1) /root/.bashrc 里 anaconda/PATH 出现在哪 ==="
grep -n "anaconda\|conda\|PATH=" /root/.bashrc 2>/dev/null
echo "--- 交互式早退守卫在第几行 ---"
grep -n 'case \$- in' -A3 /root/.bashrc 2>/dev/null

echo
echo "=== 2) /root/.profile 是否 source .bashrc ==="
cat /root/.profile 2>/dev/null | tail -12

echo
echo "=== 3) sudoers 关键配置 ==="
grep -rnE "secure_path|env_reset|env_keep|env_delete" /etc/sudoers /etc/sudoers.d/ 2>/dev/null
echo "--- /etc/sudoers.d 现有文件 ---"
ls -la /etc/sudoers.d/ 2>/dev/null

echo
echo "=== 4) /etc/profile.d 里的 anaconda ==="
ls /etc/profile.d/ 2>/dev/null
grep -rln "anaconda" /etc/profile.d/ /etc/profile /etc/bash.bashrc 2>/dev/null

echo
echo "=== 5) 各种 sudo 形式的实测矩阵 ==="
t() { printf "  %-46s " "$1"; shift; out=$(eval "$@" 2>&1 | tr -d '\n'); echo "${out:-<空>}"; }
t "sudo bash -c"                 "sudo bash -c 'command -v pip3 || echo NOT_FOUND'"
t "sudo sh -c"                   "sudo sh -c 'command -v pip3 || echo NOT_FOUND'"
t "sudo -s <cmd>"                "sudo -s 'command -v pip3 || echo NOT_FOUND'"
t "sudo -i <cmd>"                "sudo -i 'command -v pip3 || echo NOT_FOUND'"
t "sudo -E bash -c"              "sudo -E bash -c 'command -v pip3 || echo NOT_FOUND'"
t "sudo env PATH=anaconda:<cur>" "sudo env PATH=/root/anaconda3/bin:\$PATH bash -c 'command -v pip3'"
t "sudo bash -lc"                "sudo bash -lc 'command -v pip3 || echo NOT_FOUND'"
t "sudo bash -ic"                "sudo bash -ic 'command -v pip3 || echo NOT_FOUND'"
t "sudo -H bash -c"              "sudo -H bash -c 'command -v pip3 || echo NOT_FOUND'"
t "直接 root shell 下"            "command -v pip3 || echo NOT_FOUND"
echo "  --- 各自看到的 PATH ---"
t "sudo bash -c 'echo \$PATH'"   "sudo bash -c 'echo \$PATH'"
t "sudo -i 'echo \$PATH'"        "sudo -i 'echo \$PATH'"
t "sudo -s 'echo \$PATH'"        "sudo -s 'echo \$PATH'"

echo
echo "=== 6) sudo -l 输出（含环境相关）==="
sudo -l 2>&1 | grep -iE "secure_path|env_|PATH" | head -10
