#!/bin/bash
# 在远端以 root 身份执行（通过 ssh kylin-111）
echo "########## 1. root 身份确认 ##########"
whoami; hostname; id

echo
echo "########## 2. sshd 关键配置 ##########"
grep -inE "PermitRootLogin|PubkeyAuthentication|PasswordAuthentication|AuthorizedKeysFile|ChallengeResponse" /etc/ssh/sshd_config | sed 's/^/  /'
echo "--- 是否有 include 的子配置覆盖 ---"
ls /etc/ssh/sshd_config.d/ 2>/dev/null | sed 's/^/  /' || echo "  无 sshd_config.d"

echo
echo "########## 3. root 的 SSH 目录权限 ##########"
ls -la /root/.ssh/ | sed 's/^/  /'
echo "  authorized_keys 指纹:"
ssh-keygen -lf /root/.ssh/authorized_keys 2>&1 | sed 's/^/    /'

echo
echo "########## 4. root 登录时用的 shell ##########"
getent passwd root | sed 's/^/  /'

echo
echo "########## 5. VSCode Server 在 root 下的状态 ##########"
ls -d /root/.vscode-server 2>/dev/null && echo "  已存在（重连会复用）" || echo "  尚未安装（首次连接时 VSCode 会自动装）"
ls -la /root/.vscode-server 2>/dev/null | head -8 | sed 's/^/  /'

echo
echo "########## 6. 当前 vscode-server 进程（哪个用户）##########"
ps -eo user,pid,cmd 2>/dev/null | grep "[v]scode-server" | head -5 | sed 's/^/  /' || echo "  无"

echo
echo "########## 7. 当前容器状态（提醒：之前重置的后续）##########"
docker ps -a --format '  {{.Names}}  {{.Status}}' 2>&1 | head -10
echo "  镜像数: $(docker images -q 2>/dev/null | wc -l)"
echo "  容器目录数: $(ls /deploy/docker/containers/ 2>/dev/null | wc -l)"
