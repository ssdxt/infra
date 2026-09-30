#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "========== 最终验收 =========="
echo "--- 节点"
kubectl get nodes --no-headers 2>&1 | awk '{print $2}' | sort | uniq -c
echo "--- monitoring 命名空间"
kubectl get pods -n monitoring --no-headers 2>&1 | awk '{print $2, $3}' | sort | uniq -c
echo "--- cert-manager"
kubectl get pods -n cert-manager --no-headers 2>&1 | awk '{print $2, $3}' | sort | uniq -c
echo "--- gatewayclass"
kubectl get gatewayclass --no-headers 2>&1
echo "--- KPR"
kubectl -n kube-system exec ds/cilium -c cilium-agent -- cilium-dbg status 2>/dev/null | grep -E 'KubeProxyReplacement' | head -1
echo "--- 全集群非Running"
kubectl get pods -A --no-headers 2>/dev/null | grep -v -E 'Running|Completed' | head -4 || echo ALL-RUNNING
echo ""
echo "--- 保存 helm values（离线复刻用）"
mkdir -p /data1/ssdxt/values
helm get values prometheus-stack -n monitoring -o yaml > /data1/ssdxt/values/prometheus-stack-values.yaml 2>/dev/null && echo "prometheus-stack values 已保存"
helm get values cert-manager -n cert-manager -o yaml > /data1/ssdxt/values/cert-manager-values.yaml 2>/dev/null && echo "cert-manager values 已保存"
helm get values cilium -n kube-system -o yaml > /data1/ssdxt/values/cilium-values.yaml 2>/dev/null && echo "cilium values 已保存"
ls -la /data1/ssdxt/values/ 2>/dev/null | tail -4