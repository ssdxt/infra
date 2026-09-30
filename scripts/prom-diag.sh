#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== Prometheus init 容器镜像与错误"
kubectl get pod prometheus-prometheus-stack-kube-prom-prometheus-0 -n monitoring -o jsonpath='{.spec.initContainers[*].image}' 2>&1; echo
kubectl describe pod prometheus-prometheus-stack-kube-prom-prometheus-0 -n monitoring 2>&1 | grep -A3 -E 'RunContainerError|Error' | head -8