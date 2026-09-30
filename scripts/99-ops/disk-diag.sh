#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== 1. 全集群根盘水位一览（11 台）====="
for ip in 10.100.10.10 10.100.10.14 10.100.10.19 10.100.10.33 10.100.10.34 10.100.10.39 10.100.10.41 10.100.10.44 10.100.10.45 10.100.10.46 10.100.10.47; do
  echo -n "  [$ip] "
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=6 root@$ip \
    'df -h / | tail -1 | awk "{print \"根盘已用 \"\$3\"/\"\$2\" (\"\$5\")\"}"' 2>/dev/null
done
echo ""
echo "===== 2. .44 根盘 TOP 消费者 ====="
ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@10.100.10.44 '
  echo "  --- 一级目录占用 TOP10"
  du -x -d1 -h / 2>/dev/null | sort -rh | head -10 | sed "s/^/  /"
  echo "  --- containerd 内容"
  du -sh /var/lib/containerd 2>/dev/null | sed "s/^/    /"
  crictl images 2>/dev/null | wc -l | awk "{print \"    镜像数: \"\$1}"
  crictl imagefsinfo 2>/dev/null | grep -E "usedBytes|usedPercent" | sed "s/^/    /"
  echo "  --- 日志"
  du -sh /var/log /var/log/pods 2>/dev/null | sed "s/^/    /"
  journalctl --disk-usage 2>/dev/null | sed "s/^/    /"
  echo "  --- 最近 24h 变化的 大文件(>100M)"
  find / -xdev -type f -size +100M -mmin -1440 2>/dev/null | head -10 | sed "s/^/    /"
  echo "  --- 增长最快的目录（找写入源）"
  find / -xdev -type f -mmin -360 -size +10M 2>/dev/null -exec du -h {} \; 2>/dev/null | sort -rh | head -8 | sed "s/^/    /"
' 2>&1 | sed 's/^/  /'
echo ""
echo "===== 3. 是谁在这个节点拉镜像/写盘（事件）====="
kubectl get events -A --field-selector involvedObject.nodeName=wxq-run-06 2>/dev/null --sort-by=.lastTimestamp | tail -8 | awk '{print "  "$1, $4, $6, $7}' 2>/dev/null
echo ""
echo "===== 4. 安全清理（不动在用镜像，避开升级窗口）====="
ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@10.100.10.44 '
  echo -n "  journal 收缩: "; journalctl --vacuum-size=150M 2>/dev/null | tail -1
  echo -n "  apt 缓存清理: "; apt-get clean 2>/dev/null; echo "完成"
  echo -n "  已 Exited 容器清理: "; crictl ps -a -q --state Exited 2>/dev/null | while read c; do crictl rm "$c" 2>/dev/null; done | wc -l
' 2>&1 | sed 's/^/  /'
echo ""
echo -n "  清理后根盘: "
ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@10.100.10.44 'df -h / | tail -1' 2>/dev/null
echo ""
echo "===== 5. 全集群 containerd 根目录规划核对（结构解法的依据）====="
for ip in 10.100.10.33 10.100.10.44; do
  echo -n "  [$ip] /data1 可用: "
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$ip 'df -h /data1 2>/dev/null | tail -1 | awk "{print \$4}"' 2>/dev/null
  echo -n "         / (根盘) 总量: "
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$ip 'df -h / 2>/dev/null | tail -1 | awk "{print \$2}"' 2>/dev/null
done