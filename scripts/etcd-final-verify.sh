#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== 1. etcd 慢盘告警是否消失（迁移后日志 vs 之前每小时上千条）====="
for ip in 10.100.10.10 10.100.10.14 10.100.10.19; do
  echo -n "  [$ip] 迁移后 slow fdatasync 条数: "
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$ip \
    'journalctl -u etcd --since "20 minutes ago" 2>/dev/null | grep -c "slow fdatasync"' 2>/dev/null
done
echo ""
echo "===== 2. etcd 运行状态（leader/提案提交延迟）====="
for ip in 10.100.10.10 10.100.10.14 10.100.10.19; do
  echo -n "  [$ip] "
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$ip \
    'etcdctl --cacert=/etc/kubernetes/pki/etcd/ca.crt --cert=/etc/kubernetes/pki/etcd/client.crt --key=/etc/kubernetes/pki/etcd/client.key --endpoints=https://'$ip':2379 endpoint status -w table 2>/dev/null | tail -2 | head -1' 2>/dev/null
done
echo ""
echo "===== 3. 当前告警 ====="
kubectl -n monitoring exec alertmanager-prometheus-stack-kube-prom-alertmanager-0 -c alertmanager -- \
  wget -qO- 'http://localhost:9093/api/v2/alerts?active=true&silenced=false' 2>/dev/null | python3 -c '
import sys, json
from collections import Counter
d = json.load(sys.stdin)
c = Counter((a["labels"].get("severity"), a["labels"].get("alertname")) for a in d)
for (sev, name), n in sorted(c.items()): print("  [%s] %s x%d" % (sev, name, n))
'
echo ""
echo "===== 4. 归档执行脚本 ====="
cp /tmp/etcd-cutover.sh /data1/ssdxt/storage/05b-etcd-cutover-executed.sh 2>/dev/null && echo "  已归档 /data1/ssdxt/storage/05b-etcd-cutover-executed.sh"
echo ""
echo "===== 5. 挂载持久化复核（fstab 无 nofail、有 UUID、drop-in 在位）====="
for ip in 10.100.10.10 10.100.10.14 10.100.10.19; do
  echo -n "  [$ip] "
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$ip \
    'grep "/var/lib/etcd" /etc/fstab | head -1; ls /etc/systemd/system/etcd.service.d/require-mount.conf >/dev/null 2>&1 && echo -n " drop-in✓"; grep -c nofail /etc/fstab | sed "s/^/ fstab含nofail行数=/"' 2>/dev/null
  echo ""
done