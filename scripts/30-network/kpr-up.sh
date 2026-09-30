#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
cd /data1/ssdxt
echo "=== 备份当前 values"
helm get values cilium -n kube-system -o yaml > /data1/ssdxt/cilium-values-before-kpr.yaml 2>/dev/null
wc -l /data1/ssdxt/cilium-values-before-kpr.yaml
echo "=== helm upgrade 开启 KPR"
helm upgrade cilium /data1/ssdxt/charts/cilium-1.20.1.tgz -n kube-system \
  -f /data1/ssdxt/cilium-values-before-kpr.yaml \
  --set kubeProxyReplacement=true \
  --set k8sServiceHost=10.100.10.250 \
  --set k8sServicePort=6443 \
  --set gatewayAPI.enabled=true \
  --timeout 15m 2>&1 | tail -6
echo "=== 等待 Cilium 滚动（90秒）"
sleep 90
echo "=== Cilium 状态"
kubectl -n kube-system exec ds/cilium -c cilium-agent -- cilium-dbg status --brief 2>/dev/null | head -2
echo "=== KPR 模式确认"
kubectl -n kube-system exec ds/cilium -c cilium-agent -- cilium-dbg status 2>/dev/null | grep -E 'KubeProxyReplacement|Routing' | head -3
echo "=== ConfigMap 确认"
kubectl get cm cilium-config -n kube-system -o jsonpath='{.data.kube-proxy-replacement} {.data.k8s-service-host} {.data.k8s-service-port}' 2>&1; echo