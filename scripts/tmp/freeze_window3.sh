#!/bin/bash
echo "########## A. 当前启动周期 kern.log 里那段异常内核输出（带上下文）##########"
sudo grep -an '' /var/log/kern.log | sed -n "$(sudo grep -an '146\.26' /var/log/kern.log | head -1 | cut -d: -f1 | awk '{print $1-15}'),+60p" 2>/dev/null | head -80

echo
echo "########## B. 各启动周期 是否有 hung task / lockup / oom / panic ##########"
for k in 'hung_task' 'blocked for more than' 'soft lockup' 'hard lockup' 'rcu_sched' 'rcu_preempt' 'stall' 'oom-kill' 'Out of memory' 'Killed process' 'page allocation failure' 'panic' 'Oops' 'BUG:'; do
  n=$(sudo grep -aci "$k" /var/log/syslog /var/log/kern.log 2>/dev/null | awk -F: '{s+=$2} END{print s+0}')
  echo "  $k : $n"
done

echo
echo "########## C. syslog 里所有含 hung/OOM/lockup 的行（全历史）##########"
sudo grep -aiE 'hung task|blocked for more than|soft lockup|hard lockup|rcu.*stall|oom-kill|Out of memory|Killed process|page allocation failure' /var/log/syslog /var/log/kern.log 2>/dev/null | tail -25

echo
echo "########## D. coredump 记录 ##########"
sudo ls -la /var/lib/systemd/coredump/ 2>/dev/null | tail -15
echo "--- coredump 计数 ---"
sudo ls /var/lib/systemd/coredump/ 2>/dev/null | wc -l
echo "--- coredump 存储占用 ---"
sudo du -sh /var/lib/systemd/coredump/ 2>/dev/null
echo "--- journald 里 coredump 事件（本周期）---"
sudo journalctl -b -p err --no-pager 2>&1 | grep -aiE 'coredump|core dump|segfault|dumped core' | tail -10

echo
echo "########## E. 08:32 那个周期里 load / 内存压力的痕迹 ##########"
sudo awk '/^Sep 14 08:3[3-9]:|^Sep 14 08:4[0-9]:|^Sep 14 0[89]:/ {print}' /var/log/syslog 2>/dev/null | grep -aiE 'oom|memory|swap|kill|coredump|dump' | tail -20
