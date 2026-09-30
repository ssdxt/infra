#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== kube-proxy 配置模式"
kubectl get cm kube-proxy -n kube-system -o jsonpath='{.data.config\.conf}' 2>/dev/null | grep -E 'mode|clusterCIDR' | head -3
echo "=== kube-proxy Pod 状态（重启次数）"
kubectl get pods -n kube-system -l k8s-app=kube-proxy --no-headers 2>&1 | awk '{print $1, $2, $4}' | head -12
echo "=== nodelocaldns 状态"
kubectl get ds nodelocaldns -n kube-system --no-headers 2>&1 | head -2
kubectl get pods -n kube-system -l k8s-app=nodelocaldns --no-headers 2>&1 | awk '{print $1, $2, $4}' | head -12
echo "=== nodelocaldns 配置的上游"
kubectl get cm nodelocaldns -n kube-system -o jsonpath='{.data.Corefile}' 2>/dev/null | head -12
echo "=== 节点上的 nftables 规则量（kube-proxy 是否编程成功）"
ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@10.100.10.33 'nft list ruleset 2>/dev/null | grep -c kube; ipvsadm -Ln 2>/dev/null | head -3' 2>/dev/null
echo "=== iptables nat 表 KUBE 链"
ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@10.100.10.33 'iptables -t nat -L KUBE-SERVICES -n 2>/dev/null | head -5; echo ---; iptables -t nat -L -n 2>/dev/null | grep -c KUBE' 2>/dev/null