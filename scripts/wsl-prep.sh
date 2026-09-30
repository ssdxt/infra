#!/bin/bash
set -e
mkdir -p /mnt/e/ZP-工作信息/infra-tool-ssdxt/kubernetes/kubekey/oneclick/charts 2>/dev/null || mkdir -p ~/charts
WORK=~/charts; mkdir -p $WORK
cd $WORK
echo "== helm repo add"
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>&1 | tail -1
helm repo add jetstack https://charts.jetstack.io 2>&1 | tail -1
helm repo add cilium https://helm.cilium.io 2>&1 | tail -1
echo "== 下载 charts"
helm pull prometheus-community/kube-prometheus-stack --version 62.7.0 2>&1 | tail -2
helm pull jetstack/cert-manager --version v1.16.1 2>&1 | tail -2
helm pull cilium/cilium --version 1.20.1 2>&1 | tail -2
ls -la $WORK/*.tgz
echo "== 下载 gateway-api CRD (experimental v1.2.1 - 含 TLSRoute v1)"
mkdir -p $WORK/gateway-api
for f in gateway.networking.k8s.io_gatewayclasses gateway.networking.k8s.io_gateways gateway.networking.k8s.io_httproutes gateway.networking.k8s.io_referencegrants gateway.networking.k8s.io_tlsroutes; do
  curl -sL -o $WORK/gateway-api/$f.yaml https://raw.githubusercontent.com/kubernetes-sigs/gateway-api/v1.2.1/config/crd/experimental/$f.yaml && echo "  got $f"
done
ls -la $WORK/gateway-api/
