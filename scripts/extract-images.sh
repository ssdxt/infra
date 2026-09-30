#!/bin/bash
# 提取 Longhorn / Loki 图表所需的全部镜像（供 skopeo 搬运）
export no_proxy='10.100.10.0/24,harbor.wuxing.local,localhost,127.0.0.1'
mkdir -p /home/cc/charts2 && cd /home/cc/charts2

echo "=== 下载 Longhorn & Loki 图表 ==="
helm repo add longhorn https://charts.longhorn.io 2>&1 | tail -1
helm repo add grafana https://grafana.github.io/helm-charts 2>&1 | tail -1
helm repo add nfs-subdir https://kubernetes-sigs.github.io/nfs-subdir-external-provisioner 2>&1 | tail -1
helm repo update >/dev/null 2>&1

helm pull longhorn/longhorn --version 1.7.2 2>&1 | tail -1
helm pull grafana/loki --version 6.24.0 2>&1 | tail -1
helm pull grafana/alloy --version 0.12.0 2>&1 | tail -1
helm pull nfs-subdir/nfs-subdir-external-provisioner --version 4.0.18 2>&1 | tail -1
ls -1 *.tgz 2>/dev/null

echo ""
echo "=== Longhorn 镜像 ==="
helm template lh longhorn-1.7.2.tgz --namespace longhorn-system 2>/dev/null \
  | grep -oE 'image: [^ ]+' | sed 's/image: //' | tr -d '"' | grep -vE '^\$' | sort -u

echo ""
echo "=== Loki 镜像 ==="
helm template lk loki-6.24.0.tgz --namespace logging 2>/dev/null \
  | grep -oE 'image: [^ ]+' | sed 's/image: //' | tr -d '"' | grep -vE '^\$' | sort -u

echo ""
echo "=== Alloy 镜像 ==="
helm template al alloy-0.12.0.tgz --namespace logging 2>/dev/null \
  | grep -oE 'image: [^ ]+' | sed 's/image: //' | tr -d '"' | grep -vE '^\$' | sort -u

echo ""
echo "=== NFS provisioner 镜像 ==="
helm template np nfs-subdir-external-provisioner-4.0.18.tgz --namespace kube-system 2>/dev/null \
  | grep -oE 'image: [^ ]+' | sed 's/image: //' | tr -d '"' | grep -vE '^\$' | sort -u
