#!/bin/bash
# ============================================================
# skopeo 批量搬运镜像到 Harbor（amd64 单架构）
# 用法: bash mirror.sh [组件名]     # 不传参数=全部
# 组件: longhorn | logging | metrics | nfs | all
# ============================================================
export NO_PROXY='harbor.wuxing.local,10.100.10.29,localhost,127.0.0.1'
export no_proxy="$NO_PROXY"

H=harbor.wuxing.local
USER=admin
PASS='<HARBOR_PASSWORD>'
TARGET=${1:-all}
LOG=/tmp/mirror-$(date +%m%d-%H%M).log

# ---------- 镜像清单：上游|Harbor目标 ----------
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
'

LIST_METRICS='
registry.k8s.io/metrics-server/metrics-server:v0.7.2|metrics-server/metrics-server:v0.7.2
'

LIST_NFS='
registry.k8s.io/sig-storage/nfs-subdir-external-provisioner:v4.0.2|nfs-provisioner/nfs-subdir-external-provisioner:v4.0.2
'

case "$TARGET" in
  longhorn) LIST="$LIST_LONGHORN" ;;
  logging)  LIST="$LIST_LOGGING" ;;
  metrics)  LIST="$LIST_METRICS" ;;
  nfs)      LIST="$LIST_NFS" ;;
  all)      LIST="$LIST_LONGHORN$LIST_LOGGING$LIST_METRICS$LIST_NFS" ;;
  *) echo "未知组件: $TARGET"; exit 1 ;;
esac

# ---------- 建 Harbor 项目 ----------
for p in longhorn logging metrics-server nfs-provisioner; do
  curl -sk -o /dev/null -u "$USER:$PASS" -H 'Content-Type: application/json' \
    -X POST "https://$H/api/v2.0/projects" -d "{\"project_name\":\"$p\",\"public\":true}"
done

echo "=== 开始搬运（目标: $TARGET）$(date +%T) ===" | tee -a "$LOG"
OK=0; FAIL=0
for line in $LIST; do
  [ -z "$line" ] && continue
  src="${line%%|*}"; dst="${line##*|}"
  # 跳过已存在的
  if skopeo inspect --tls-verify=false --creds "$USER:$PASS" "docker://$H/$dst" >/dev/null 2>&1; then
    echo "  跳过(已存在) $dst" | tee -a "$LOG"; OK=$((OK+1)); continue
  fi
  echo -n "  搬运 $src -> $dst ... " | tee -a "$LOG"
  if skopeo copy --override-arch amd64 --override-os linux \
      --dest-tls-verify=false --dest-creds "$USER:$PASS" \
      "docker://$src" "docker://$H/$dst" >>"$LOG" 2>&1; then
    echo "OK" | tee -a "$LOG"; OK=$((OK+1))
  else
    echo "失败(见日志)" | tee -a "$LOG"; FAIL=$((FAIL+1))
  fi
done
echo "=== 完成 $(date +%T)  成功:$OK 失败:$FAIL ===" | tee -a "$LOG"
echo "日志: $LOG"
