#!/bin/bash
export no_proxy='10.100.10.0/24,harbor.wuxing.local,localhost,127.0.0.1'
docker pull quay.io/prometheus-operator/prometheus-config-reloader:v0.76.1 2>&1 | tail -1
mkdir -p /mnt/e/ZP-工作信息/infra-tool-ssdxt/kubernetes/kubekey/oneclick/offline
docker save quay.io/prometheus-operator/prometheus-config-reloader:v0.76.1 -o "/mnt/e/ZP-工作信息/infra-tool-ssdxt/kubernetes/kubekey/oneclick/offline/reloader.tar" && ls -lh "/mnt/e/ZP-工作信息/infra-tool-ssdxt/kubernetes/kubekey/oneclick/offline/reloader.tar"