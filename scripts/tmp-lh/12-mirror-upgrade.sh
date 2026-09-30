#!/bin/bash
set -u
export HTTPS_PROXY=http://127.0.0.1:12450
export NO_PROXY='harbor.wuxing.local,10.100.10.29,localhost,127.0.0.1'
export no_proxy="$NO_PROXY"
LOG=~/longhorn-mirror-upgrade.log
: > $LOG
ok=0; fail=0
copy() {
  src=$1; dst=$2
  if skopeo inspect --tls-verify=false --creds admin:<HARBOR_PASSWORD> "docker://harbor.wuxing.local/$dst" >/dev/null 2>&1; then
    echo "SKIP $dst (exists)" >> $LOG; ok=$((ok+1)); return
  fi
  if skopeo copy --override-arch amd64 --retry-times 3 \
      --src docker --dest docker --dest-tls-verify=false --dest-creds admin:<HARBOR_PASSWORD> \
      "docker://$src" "docker://harbor.wuxing.local/$dst" >> $LOG 2>&1; then
    echo "OK $dst" >> $LOG; ok=$((ok+1))
  else
    echo "FAIL $dst" >> $LOG; fail=$((fail+1))
  fi
}
gen() { # version
  v=$1
  for name in longhorn-engine longhorn-manager longhorn-ui longhorn-instance-manager longhorn-share-manager backing-image-manager; do
    copy "docker.io/longhornio/$name:v$v" "longhorn/$name:v$v"
  done
}
# engine/manager/ui/instance/share/backing per version
for v in 1.8.2 1.9.2 1.10.2 1.11.3 1.12.1 1.13.0; do gen $v; done
# support-bundle-kit & csi sidecars per version
copy docker.io/longhornio/support-bundle-kit:v0.0.56 longhorn/support-bundle-kit:v0.0.56
copy docker.io/longhornio/support-bundle-kit:v0.0.69 longhorn/support-bundle-kit:v0.0.69
copy docker.io/longhornio/support-bundle-kit:v0.0.79 longhorn/support-bundle-kit:v0.0.79
copy docker.io/longhornio/support-bundle-kit:v0.0.88 longhorn/support-bundle-kit:v0.0.88
copy docker.io/longhornio/support-bundle-kit:v0.0.92 longhorn/support-bundle-kit:v0.0.92
copy docker.io/longhornio/support-bundle-kit:v0.0.98 longhorn/support-bundle-kit:v0.0.98
copy docker.io/longhornio/csi-attacher:v4.9.0 longhorn/csi-attacher:v4.9.0
copy docker.io/longhornio/csi-provisioner:v5.3.0 longhorn/csi-provisioner:v5.3.0
copy docker.io/longhornio/csi-node-driver-registrar:v2.14.0 longhorn/csi-node-driver-registrar:v2.14.0
copy docker.io/longhornio/csi-resizer:v1.13.2 longhorn/csi-resizer:v1.13.2
copy docker.io/longhornio/csi-snapshotter:v8.2.0 longhorn/csi-snapshotter:v8.2.0
copy docker.io/longhornio/livenessprobe:v2.16.0 longhorn/livenessprobe:v2.16.0
copy docker.io/longhornio/csi-attacher:v4.9.0-20250709 longhorn/csi-attacher:v4.9.0-20250709
copy docker.io/longhornio/csi-provisioner:v5.3.0-20250709 longhorn/csi-provisioner:v5.3.0-20250709
copy docker.io/longhornio/csi-node-driver-registrar:v2.14.0-20250709 longhorn/csi-node-driver-registrar:v2.14.0-20250709
copy docker.io/longhornio/csi-resizer:v1.14.0-20250709 longhorn/csi-resizer:v1.14.0-20250709
copy docker.io/longhornio/csi-snapshotter:v8.3.0-20250709 longhorn/csi-snapshotter:v8.3.0-20250709
copy docker.io/longhornio/livenessprobe:v2.16.0-20250709 longhorn/livenessprobe:v2.16.0-20250709
copy docker.io/longhornio/csi-attacher:v4.10.0-20251226 longhorn/csi-attacher:v4.10.0-20251226
copy docker.io/longhornio/csi-provisioner:v5.3.0-20251226 longhorn/csi-provisioner:v5.3.0-20251226
copy docker.io/longhornio/csi-node-driver-registrar:v2.15.0-20251226 longhorn/csi-node-driver-registrar:v2.15.0-20251226
copy docker.io/longhornio/csi-resizer:v1.14.0-20260119 longhorn/csi-resizer:v1.14.0-20260119
copy docker.io/longhornio/csi-snapshotter:v8.4.0-20251226 longhorn/csi-snapshotter:v8.4.0-20251226
copy docker.io/longhornio/livenessprobe:v2.17.0-20251226 longhorn/livenessprobe:v2.17.0-20251226
copy docker.io/longhornio/csi-attacher:v4.12.0 longhorn/csi-attacher:v4.12.0
copy docker.io/longhornio/csi-provisioner:v6.3.0 longhorn/csi-provisioner:v6.3.0
copy docker.io/longhornio/csi-node-driver-registrar:v2.17.0 longhorn/csi-node-driver-registrar:v2.17.0
copy docker.io/longhornio/csi-resizer:v2.2.0 longhorn/csi-resizer:v2.2.0
copy docker.io/longhornio/csi-snapshotter:v8.6.0 longhorn/csi-snapshotter:v8.6.0
copy docker.io/longhornio/livenessprobe:v2.19.0 longhorn/livenessprobe:v2.19.0
copy docker.io/longhornio/csi-resizer:v2.2.1 longhorn/csi-resizer:v2.2.1
copy docker.io/longhornio/csi-attacher:v4.13.0 longhorn/csi-attacher:v4.13.0
copy docker.io/longhornio/csi-node-driver-registrar:v2.18.0 longhorn/csi-node-driver-registrar:v2.18.0
copy docker.io/longhornio/livenessprobe:v2.20.0 longhorn/livenessprobe:v2.20.0
# snapshot-controller (缺失的 VS->VSC controller, 匹配 v8.0.1 CRD)
copy registry.k8s.io/sig-storage/snapshot-controller:v8.0.1 longhorn/snapshot-controller:v8.0.1
echo "DONE ok=$ok fail=$fail" >> $LOG
