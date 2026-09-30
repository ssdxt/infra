#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== 实际请求的镜像"
kubectl get pod prometheus-prometheus-stack-kube-prom-prometheus-0 -n monitoring -o jsonpath='{.spec.containers[*].image}' 2>&1; echo
kubectl get pod alertmanager-prometheus-stack-kube-prom-alertmanager-0 -n monitoring -o jsonpath='{.spec.containers[*].image}' 2>&1; echo
echo "=== 拉取错误"
kubectl describe pod prometheus-prometheus-stack-kube-prom-prometheus-0 -n monitoring 2>&1 | grep -A2 -E 'Failed|not found|denied|unauthorized' | tail -6
echo "=== Harbor 里实际有的 tag"
curl -sk -u admin:<HARBOR_PASSWORD> 'https://harbor.wuxing.local/v2/monitoring/prometheus/tags/list' 2>/dev/null; echo
curl -sk -u admin:<HARBOR_PASSWORD> 'https://harbor.wuxing.local/v2/monitoring/alertmanager/tags/list' 2>/dev/null; echo