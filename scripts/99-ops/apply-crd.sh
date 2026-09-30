#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
cd /data1/ssdxt/charts/gateway-api
echo "=== 应用 v1.6.1 CRD"
kubectl apply -f experimental-install.yaml 2>&1 | tail -5
echo "=== CRD 版本确认"
kubectl get crd tlsroutes.gateway.networking.k8s.io -o jsonpath='{.spec.versions[*].name}' 2>&1; echo
kubectl get crd grpcroutes.gateway.networking.k8s.io -o jsonpath='{.spec.versions[*].name}' 2>&1; echo
kubectl get crd referencegrants.gateway.networking.k8s.io -o jsonpath='{.spec.versions[*].name}' 2>&1; echo
kubectl get crd backendtlspolicies.gateway.networking.k8s.io -o jsonpath='{.spec.versions[*].name}' 2>&1; echo
echo "=== 重启 operator 激活 gateway 控制器"
kubectl -n kube-system rollout restart deploy/cilium-operator 2>&1 | tail -1
sleep 60
echo "=== gatewayclass"
kubectl get gatewayclass 2>&1
kubectl get gatewayclass cilium -o jsonpath='{.status.conditions[0].status} / {.status.conditions[0].reason}' 2>&1; echo
echo "=== operator gateway 日志"
kubectl logs -n kube-system -l io.cilium/app=operator --tail=60 2>/dev/null | grep -iE 'gateway' | tail -4