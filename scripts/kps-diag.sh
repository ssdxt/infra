#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== 实际使用的镜像（未生效的会显示 quay.io/registry.k8s.io）"
kubectl get ds prometheus-stack-prometheus-node-exporter -n monitoring -o jsonpath='{.spec.template.spec.containers[0].image}' 2>&1; echo
kubectl get deploy prometheus-stack-kube-state-metrics -n monitoring -o jsonpath='{.spec.template.spec.containers[0].image}' 2>&1; echo
kubectl get deploy prometheus-stack-grafana -n monitoring -o jsonpath='{.spec.template.spec.containers[*].image}' 2>&1; echo
kubectl get deploy prometheus-stack-kube-prom-operator -n monitoring -o jsonpath='{.spec.template.spec.containers[*].image}' 2>&1; echo
echo "=== chart 里 node-exporter / ksm 的真实 values 键"
cd /tmp && rm -rf kpsv && mkdir kpsv && tar xzf /data1/ssdxt/charts/kube-prometheus-stack-62.7.0.tgz -C kpsv 2>/dev/null
grep -n -A5 '^prometheus-node-exporter:' kpsv/kube-prometheus-stack/values.yaml | head -12
grep -n -A6 '^kube-state-metrics:' kpsv/kube-prometheus-stack/values.yaml | head -14
echo "=== cilium-operator 崩溃原因"
kubectl logs -n kube-system -l io.cilium/app=operator --tail=6 2>/dev/null | tail -5
kubectl get pods -n kube-system -l io.cilium/app=operator --no-headers 2>&1 | awk '{print $1, $2, $3, $5}'