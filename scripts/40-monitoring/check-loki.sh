#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== loki-0 Pending 原因 ====="
kubectl -n logging get pod loki-0 -o json | python3 -c '
import sys, json
d = json.load(sys.stdin)
p = d["status"]
print("  phase:", p.get("phase"))
for c in p.get("conditions", []):
    if c["status"] == "False":
        print("  ❌", c.get("reason"), "-", c.get("message","")[:200])
for e in d.get("status", {}).get("conditions", []): pass
'
kubectl -n logging describe pod loki-0 2>/dev/null | tail -15 | sed 's/^/  /'
echo ""
echo "===== 修复仓库推送（pull --rebase 后推）====="
cd /data1/ssdxt/ || true
git -C /tmp/infra-sync 2>/dev/null || true
# 在 control-01 没有 clone；用工作站那边的逻辑不行——改在本机临时 clone 拉远端合并？简化：直接本地 infra-repo 由工作站侧处理
echo "（仓库修复在工作站侧执行）"