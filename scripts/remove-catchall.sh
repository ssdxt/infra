#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== 1. 备份并删除兜底路由 monitoring-routes ====="
kubectl -n gateway get httproute monitoring-routes -o yaml > /data1/ssdxt/gateway/backup/monitoring-routes-$(date +%m%d-%H%M).yaml 2>/dev/null \
  && echo "  已备份到 /data1/ssdxt/gateway/backup/"
kubectl -n gateway delete httproute monitoring-routes 2>&1 | tail -1 | sed 's/^/  /'
echo ""
echo "===== 2. 验证：IP 直连（应不再落到 Grafana）====="
echo -n "  http://10.100.10.10:32299 (无 Host 匹配) : "
curl -s -o /dev/null -w '%{http_code}' --noproxy '*' -m 8 http://10.100.10.10:32299/ 2>/dev/null; echo "  (404=已无兜底 ✅)"
echo ""
echo "===== 3. 六个域名回归（应全部不受影响）====="
for h in grafana longhorn alertmanager prometheus argocd hubble; do
  code=$(curl -sk -o /dev/null -w '%{http_code}' --noproxy '*' -m 8 --resolve $h.wuxing.local:32298:10.100.10.10 https://$h.wuxing.local:32298/ 2>/dev/null)
  echo "  https://$h.wuxing.local:32298 → $code"
done
echo ""
echo "===== 4. Longhorn Basic Auth 复核（401=认证门在工作）====="
echo -n "  无凭据: "
curl -sk -o /dev/null -w '%{http_code}' --noproxy '*' -m 8 --resolve longhorn.wuxing.local:32298:10.100.10.10 https://longhorn.wuxing.local:32298/ 2>/dev/null; echo ""
echo -n "  有凭据: "
CREDS=$(grep -oE "admin:[^ ]+" /data1/ssdxt/storage/longhorn-ui-credentials.txt 2>/dev/null | head -1)
if [ -n "$CREDS" ]; then
  curl -sk -o /dev/null -w '%{http_code}' -u "$CREDS" --noproxy '*' -m 8 --resolve longhorn.wuxing.local:32298:10.100.10.10 https://longhorn.wuxing.local:32298/ 2>/dev/null; echo ""
else
  echo "(凭据文件未找到，跳过)"
fi