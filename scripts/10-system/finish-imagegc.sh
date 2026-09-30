#!/bin/bash
# 补齐剩余 10 台节点的 kubelet 镜像 GC 配置（70/60）
NODES="10.100.10.14 10.100.10.19 10.100.10.33 10.100.10.34 10.100.10.39 10.100.10.41 10.100.10.44 10.100.10.45 10.100.10.46 10.100.10.47"
FAIL=""
for ip in $NODES; do
  echo "--- $ip"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=8 root@$ip 'bash -s' <<'REMOTE'
F=/var/lib/kubelet/config.yaml
if grep -q "imageGCHighThresholdPercent" $F 2>/dev/null; then
  echo "  已存在，跳过写入"
else
  cp -a $F $F.bak.gc.$(date +%m%d-%H%M)
  printf "\nimageGCHighThresholdPercent: 70\nimageGCLowThresholdPercent: 60\n" >> $F
fi
systemctl restart kubelet
sleep 6
if ! systemctl is-active --quiet kubelet; then
  echo "  ❌ kubelet 未启动，回滚"
  B=$(ls -t $F.bak.gc.* | head -1); cp -a "$B" $F; systemctl restart kubelet; sleep 5
  echo "  kubelet=$(systemctl is-active kubelet)"; exit 1
fi
if ! grep -q "imageGCHighThresholdPercent" $F; then echo "  ❌ 配置未写入"; exit 1; fi
echo "  ✅ kubelet=$(systemctl is-active kubelet)  配置=$(grep imageGCHigh $F | tr '\n' ' ')"
echo -n "  磁盘: "; df -h / | tail -1 | awk '{print $5}'
REMOTE
  [ $? -ne 0 ] && FAIL="$FAIL $ip"
done
echo ""
echo "===== 汇总 ====="
for ip in 10.100.10.10 10.100.10.14 10.100.10.19 10.100.10.33 10.100.10.34 10.100.10.39 10.100.10.41 10.100.10.44 10.100.10.45 10.100.10.46 10.100.10.47; do
  echo -n "  [$ip] "
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$ip \
    'grep -o "imageGCHighThresholdPercent: 70" /var/lib/kubelet/config.yaml 2>/dev/null | head -1; df -h / | tail -1 | awk "{print \"磁盘\"\$5}"' 2>/dev/null | tr '\n' ' '; echo ""
done
[ -n "$FAIL" ] && echo "❌ 失败节点:$FAIL" || echo "🎉 11 台全部完成"