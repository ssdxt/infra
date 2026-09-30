#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== 稳态复测（迁移完成 10 分钟后）====="
echo "--- 1. 最近 3 分钟 slow fdatasync（纯稳态，不含迁移干扰）"
for ip in 10.100.10.10 10.100.10.14 10.100.10.19; do
  echo -n "  [$ip] "
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$ip \
    'journalctl -u etcd --since "3 minutes ago" 2>/dev/null | grep -c "slow fdatasync"' 2>/dev/null
done
echo "--- 2. 对照：迁移前 1 小时（旧盘基线）"
for ip in 10.100.10.10 10.100.10.14 10.100.10.19; do
  echo -n "  [$ip] "
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$ip \
    'journalctl -u etcd --since "09:00" --until "09:55" 2>/dev/null | grep -c "slow fdatasync"' 2>/dev/null
done
echo ""
echo "--- 3. adapter 限流现状"
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- \
  wget -qO- 'http://localhost:9090/api/v1/query?query=sum(rate(container_cpu_cfs_throttled_periods_total%7Bpod%3D~%22prometheus-adapter.*%22%7D%5B5m%5D))%20/%20sum(rate(container_cpu_cfs_periods_total%7Bpod%3D~%22prometheus-adapter.*%22%7D%5B5m%5D))' 2>/dev/null | head -c 130; echo
echo ""
echo "--- 4. apiserver 错误预算燃烧速率（5m 窗口，越低越好）"
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- \
  wget -qO- 'http://localhost:9090/api/v1/query?query=apiserver_error_budget:burn_rate5m' 2>/dev/null | head -c 200; echo
echo "--- 5. 当前活跃告警"
kubectl -n monitoring exec alertmanager-prometheus-stack-kube-prom-alertmanager-0 -c alertmanager -- \
  wget -qO- 'http://localhost:9093/api/v2/alerts?active=true&silenced=false' 2>/dev/null | python3 -c '
import sys, json
from collections import Counter
d = json.load(sys.stdin)
c = Counter((a["labels"].get("severity"), a["labels"].get("alertname")) for a in d)
for (sev, name), n in sorted(c.items()): print("  [%s] %s x%d" % (sev, name, n))
'