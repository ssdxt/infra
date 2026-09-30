#!/bin/bash
echo "########## A. 开机自启项里谁在碰 NPU ##########"
echo "--- crontab (root/kzzk) ---"
sudo crontab -l 2>&1 | head -20
crontab -l 2>&1 | head -10
echo "--- /etc/cron.d ---"
sudo ls /etc/cron.d/ 2>/dev/null; sudo grep -rl 'ascend\|npu\|python' /etc/cron.d/ /etc/cron.daily/ 2>/dev/null | head
echo "--- rc.local ---"
sudo cat /etc/rc.local 2>/dev/null | head -20
echo "--- profile.d 里的 ascend/npu ---"
sudo ls /etc/profile.d/ 2>/dev/null | head -20

echo
echo "########## B. 最近 30 分钟内启动过、且链接了 ascend 库的进程 ##########"
for p in $(ps -eo pid --no-headers); do
  exe=$(readlink /proc/$p/exe 2>/dev/null) || continue
  case "$exe" in *python*|*pt_main*|*mindie*|*tei*|*ascend*) ;; *) continue ;; esac
  if sudo grep -qa 'libascend\|libtorch_npu\|libtbe' /proc/$p/maps 2>/dev/null; then
    echo "PID $p  $exe  START=$(ps -o lstart= -p $p 2>/dev/null)"
  fi
done 2>/dev/null | head -20

echo
echo "########## C. 当前所有 python/容器相关进程 ##########"
ps -eo pid,ppid,lstart,etime,comm,args --sort=start_time 2>/dev/null | grep -iE 'python|mindie|tei|pt_main|ascend' | grep -v grep | tail -15 | cut -c1-160

echo
echo "########## D. docker 容器启动记录（谁拉起了 glm-4-9b-chat）##########"
sudo docker inspect glm-4-9b-chat --format 'RestartPolicy={{.HostConfig.RestartPolicy.Name}} Started={{.State.StartedAt}} RestartCount={{.RestartCount}}' 2>&1
sudo docker events --since 30m --until 1s 2>/dev/null | head -15

echo
echo "########## E. 是否有 systemd timer 在拉 NPU 任务 ##########"
systemctl list-timers --all --no-pager 2>/dev/null | head -12
