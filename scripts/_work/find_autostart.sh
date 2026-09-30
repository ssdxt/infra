#!/bin/bash
echo "########## 1. systemd 系统服务 ##########"
systemctl list-unit-files 2>/dev/null | grep -iE "code|vscode" || echo "  无"

echo
echo "########## 2. systemd 用户服务（kzzk）##########"
sudo -u kzzk XDG_RUNTIME_DIR=/run/user/$(id -u kzzk) systemctl --user list-unit-files 2>/dev/null | grep -iE "code|vscode" || echo "  无"
sudo -u kzzk XDG_RUNTIME_DIR=/run/user/$(id -u kzzk) systemctl --user list-units --all 2>/dev/null | grep -iE "code|vscode" || echo "  无运行中的用户服务"

echo
echo "########## 3. crontab ##########"
echo "--- root ---"; sudo crontab -l 2>/dev/null || echo "  空"
echo "--- kzzk ---"; sudo -u kzzk crontab -l 2>/dev/null || echo "  空"
echo "--- /etc/cron.d ---"; sudo ls /etc/cron.d/ 2>/dev/null

echo
echo "########## 4. shell 启动脚本里的痕迹 ##########"
for f in /home/kzzk/.bashrc /home/kzzk/.bash_profile /home/kzzk/.profile /home/kzzk/.zshrc /root/.bashrc; do
  if sudo test -f "$f"; then
    hits=$(sudo grep -inE "vscode|code-server|remote-ssh|\.vscode-server" "$f" 2>/dev/null)
    if [ -n "$hits" ]; then echo "--- $f ---"; echo "$hits"; fi
  fi
done
echo "(无输出=干净)"

echo
echo "########## 5. sshd 的强制命令 / rc ##########"
sudo test -f /home/kzzk/.ssh/rc && echo "--- ~/.ssh/rc ---" && sudo cat /home/kzzk/.ssh/rc || echo "  无 ~/.ssh/rc"
sudo grep -inE "vscode|code-server" /etc/ssh/sshrc 2>/dev/null || echo "  无 /etc/ssh/sshrc 痕迹"
echo "--- authorized_keys 里的 command= 限制 ---"
sudo grep -c "command=" /home/kzzk/.ssh/authorized_keys 2>/dev/null || echo "  无"

echo
echo "########## 6. 桌面自启 ##########"
sudo ls -la /home/kzzk/.config/autostart/ 2>/dev/null | head -10 || echo "  无"
sudo ls -la /etc/xdg/autostart/ 2>/dev/null | grep -iE "code|vscode" || echo "  无"

echo
echo "########## 7. rc.local / init 脚本 ##########"
sudo test -f /etc/rc.local && sudo grep -inE "code|vscode" /etc/rc.local || echo "  无 /etc/rc.local 痕迹"

echo
echo "########## 8. 当前所有 VS Code 相关进程 ##########"
ps -eo pid,ppid,user,%cpu,etime,cmd 2>/dev/null | grep -E "[v]scode-server|[c]ode-server|[r]ipgrep" | head -15

echo
echo "########## 9. 磁盘占用 ##########"
sudo du -sh /home/kzzk/.vscode-server 2>/dev/null
sudo du -sh /home/kzzk/.vscode-server/cli/servers/*/ 2>/dev/null | head -5
