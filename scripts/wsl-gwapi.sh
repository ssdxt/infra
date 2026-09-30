#!/bin/bash
export no_proxy='10.100.10.0/24,harbor.wuxing.local,localhost,127.0.0.1'
mkdir -p /home/cc/gwapi && cd /home/cc/gwapi
echo "== 下载 Gateway API v1.6.1 experimental"
curl -sL -o experimental-install.yaml https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.6.1/experimental-install.yaml
ls -lh experimental-install.yaml
echo "== 包含的 CRD 与版本"
grep -E '^  name: |^    - name: v' experimental-install.yaml | head -40
echo "== 拷贝到共享盘"
cp experimental-install.yaml "/mnt/e/ZP-工作信息/infra-tool-ssdxt/kubernetes/kubekey/oneclick/offline/charts/gateway-api/"
echo COPIED