#!/bin/bash
cd /home/cc/charts
mkdir -p /mnt/e/ZP-工作信息/infra-tool-ssdxt/kubernetes/kubekey/oneclick/offline/charts
cp kube-prometheus-stack-62.7.0.tgz cert-manager-v1.16.1.tgz cilium-1.20.1.tgz /mnt/e/ZP-工作信息/infra-tool-ssdxt/kubernetes/kubekey/oneclick/offline/charts/
cp -r gateway-api /mnt/e/ZP-工作信息/infra-tool-ssdxt/kubernetes/kubekey/oneclick/offline/charts/
ls -la /mnt/e/ZP-工作信息/infra-tool-ssdxt/kubernetes/kubekey/oneclick/offline/charts/
ls /mnt/e/ZP-工作信息/infra-tool-ssdxt/kubernetes/kubekey/oneclick/offline/charts/gateway-api/