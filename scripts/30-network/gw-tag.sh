#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== nodelocaldns 镜像 tag"
curl -sk -u admin:<HARBOR_PASSWORD> 'https://harbor.wuxing.local/v2/dns/k8s-dns-node-cache/tags/list' 2>/dev/null; echo
echo "=== gatewayclass 最新状态"
kubectl get gatewayclass 2>&1
kubectl get gatewayclass cilium -o jsonpath='{.status.conditions[0].status} {.status.conditions[0].reason} {.status.conditions[0].message}' 2>&1; echo
echo "=== operator 最新日志尾部"
kubectl logs -n kube-system -l io.cilium/app=operator --tail=8 2>/dev/null | tail -4
echo "=== kube-dns service ClusterIP"
kubectl get svc kube-dns -n kube-system -o jsonpath='{.spec.clusterIP}' 2>&1; echo