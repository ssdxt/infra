#!/bin/bash
# ============================================================
# skopeo 批量搬运镜像到 Harbor（amd64 单架构）
# 用法: bash mirror.sh [longhorn|logging|metrics|nfs|argocd|monitoring|otel|keda|tetragon|all]
# 运行环境: 需要能访问外网的机器（当前用 WSL），Harbor 走 NO_PROXY 直连
# ============================================================
export NO_PROXY='harbor.wuxing.local,10.100.10.29,localhost,127.0.0.1'
export no_proxy="$NO_PROXY"
H=harbor.wuxing.local; USER=admin; PASS='<HARBOR_PASSWORD>'
TARGET=${1:-all}
LIST_LONGHORN='
longhornio/longhorn-manager:v1.7.2|longhorn/longhorn-manager:v1.7.2
longhornio/longhorn-engine:v1.7.2|longhorn/longhorn-engine:v1.7.2
longhornio/longhorn-instance-manager:v1.7.2|longhorn/longhorn-instance-manager:v1.7.2
longhornio/longhorn-share-manager:v1.7.2|longhorn/longhorn-share-manager:v1.7.2
longhornio/longhorn-ui:v1.7.2|longhorn/longhorn-ui:v1.7.2
longhornio/backing-image-manager:v1.7.2|longhorn/backing-image-manager:v1.7.2
longhornio/support-bundle-kit:v0.0.45|longhorn/support-bundle-kit:v0.0.45
longhornio/csi-attacher:v4.7.0|longhorn/csi-attacher:v4.7.0
longhornio/csi-provisioner:v4.0.1-20241007|longhorn/csi-provisioner:v4.0.1-20241007
longhornio/csi-resizer:v1.12.0|longhorn/csi-resizer:v1.12.0
longhornio/csi-snapshotter:v7.0.2-20241007|longhorn/csi-snapshotter:v7.0.2-20241007
longhornio/csi-node-driver-registrar:v2.12.0|longhorn/csi-node-driver-registrar:v2.12.0
longhornio/livenessprobe:v2.14.0|longhorn/livenessprobe:v2.14.0
'
LIST_LOGGING='
grafana/loki:3.3.2|logging/loki:3.3.2
grafana/alloy:v1.7.0|logging/alloy:v1.7.0
kiwigrid/k8s-sidecar:1.28.0|logging/k8s-sidecar:1.28.0
'
LIST_METRICS='
registry.k8s.io/metrics-server/metrics-server:v0.7.2|metrics-server/metrics-server:v0.7.2
'
LIST_NFS='
registry.k8s.io/sig-storage/nfs-subdir-external-provisioner:v4.0.2|nfs-provisioner/nfs-subdir-external-provisioner:v4.0.2
'
LIST_MONITORING='
registry.k8s.io/prometheus-adapter/prometheus-adapter:v0.12.0|monitoring/prometheus-adapter:v0.12.0
'

LIST_ARGOCD='
quay.io/argoproj/argocd:v3.5.3|argocd/argocd:v3.5.3
public.ecr.aws/docker/library/redis:8.2.3-alpine|argocd/redis:8.2.3-alpine
ghcr.io/dexidp/dex:v2.45.1|argocd/dex:v2.45.1
'
LIST_KEDA='
ghcr.io/kedacore/keda:2.21.0|keda/keda:2.21.0
ghcr.io/kedacore/keda-metrics-apiserver:2.21.0|keda/keda-metrics-apiserver:2.21.0
ghcr.io/kedacore/keda-admission-webhooks:2.21.0|keda/keda-admission-webhooks:2.21.0
'

LIST_TETRAGON='
quay.io/cilium/tetragon:v1.7.1|tetragon/tetragon:v1.7.1
quay.io/cilium/tetragon-operator:v1.7.1|tetragon/tetragon-operator:v1.7.1
quay.io/cilium/hubble-export-stdout:v1.1.1|tetragon/hubble-export-stdout:v1.1.1
quay.io/cilium/tetragon-rthooks:v0.8|tetragon/tetragon-rthooks:v0.8
'

LIST_OTEL='
ghcr.io/open-telemetry/opentelemetry-operator/opentelemetry-operator:0.159.0|otel/opentelemetry-operator:0.159.0
ghcr.io/open-telemetry/opentelemetry-collector-releases/opentelemetry-collector-k8s:0.159.0|otel/opentelemetry-collector-k8s:0.159.0
ghcr.io/open-telemetry/opentelemetry-collector-releases/opentelemetry-collector:0.159.0|otel/opentelemetry-collector:0.159.0
'
case "$TARGET" in
  longhorn) LIST="$LIST_LONGHORN";; logging) LIST="$LIST_LOGGING";;
  metrics) LIST="$LIST_METRICS";; nfs) LIST="$LIST_NFS";; argocd) LIST="$LIST_ARGOCD";; otel) LIST="$LIST_OTEL";; monitoring) LIST="$LIST_MONITORING";; keda) LIST="$LIST_KEDA";; tetragon) LIST="$LIST_TETRAGON";;
  all) LIST="$LIST_LONGHORN$LIST_LOGGING$LIST_METRICS$LIST_NFS$LIST_ARGOCD$LIST_MONITORING$LIST_OTEL$LIST_KEDA$LIST_TETRAGON";;
  *) echo "用法: bash mirror.sh [longhorn|logging|metrics|nfs|argocd|monitoring|otel|keda|tetragon|all]"; exit 1;;
esac
for p in longhorn logging metrics-server nfs-provisioner monitoring keda tetragon; do
  curl -sk -o /dev/null -u "$USER:$PASS" -H 'Content-Type: application/json' \
    -X POST "https://$H/api/v2.0/projects" -d "{\"project_name\":\"$p\",\"public\":true}"
done
OK=0; FAIL=0
for line in $LIST; do
  [ -z "$line" ] && continue
  src="${line%%|*}"; dst="${line##*|}"
  if skopeo inspect --tls-verify=false --creds "$USER:$PASS" "docker://$H/$dst" >/dev/null 2>&1; then
    echo "  跳过(已存在) $dst"; OK=$((OK+1)); continue
  fi
  echo -n "  $src -> $dst ... "
  if skopeo copy --override-arch amd64 --override-os linux \
      --dest-tls-verify=false --dest-creds "$USER:$PASS" \
      "docker://$src" "docker://$H/$dst" >/dev/null 2>&1; then
    echo OK; OK=$((OK+1))
  else
    echo 失败; FAIL=$((FAIL+1))
  fi
done
echo "完成: 成功 $OK 失败 $FAIL"
