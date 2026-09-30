#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "========== 最终验证 =========="
echo "=== 节点"
kubectl get nodes --no-headers 2>&1 | awk '{print $1, $2}'
echo "=== 非Running Pod"
kubectl get pods -A --no-headers 2>/dev/null | grep -v -E 'Running|Completed' | head -6 || echo ALL-RUNNING
echo "=== KPR"
kubectl -n kube-system exec ds/cilium -c cilium-agent -- cilium-dbg status 2>/dev/null | grep -E 'KubeProxyReplacement' | head -1
echo "=== gatewayclass"
kubectl get gatewayclass 2>&1
echo "=== kube-proxy 是否已移除"
kubectl get ds kube-proxy -n kube-system 2>&1 | tail -1
echo ""
echo "========== 安装 cert-manager =========="
helm install cert-manager /data1/ssdxt/charts/cert-manager-v1.16.1.tgz -n cert-manager --create-namespace \
  --set crds.enabled=true \
  --set image.repository=harbor.wuxing.local/cert-manager/cert-manager-controller \
  --set cainjector.image.repository=harbor.wuxing.local/cert-manager/cert-manager-cainjector \
  --set webhook.image.repository=harbor.wuxing.local/cert-manager/cert-manager-webhook \
  --set startupapicheck.image.repository=harbor.wuxing.local/cert-manager/cert-manager-startupapicheck \
  --timeout 10m 2>&1 | tail -5
echo "=== 等 90 秒"
sleep 90
echo "=== cert-manager Pod"
kubectl get pods -n cert-manager --no-headers 2>&1 | awk '{print $1, $2, $3}'