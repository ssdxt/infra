#!/bin/bash
export HTTPS_PROXY=http://127.0.0.1:12450
export NO_PROXY='harbor.wuxing.local,10.100.10.29'
export no_proxy="$NO_PROXY"
copy() {
  if skopeo inspect --tls-verify=false --creds admin:<HARBOR_PASSWORD> "docker://harbor.wuxing.local/$2" >/dev/null 2>&1; then
    echo "SKIP $2"; return
  fi
  if skopeo copy --override-arch amd64 --retry-times 3 --dest-tls-verify=false --dest-creds admin:<HARBOR_PASSWORD> \
     "docker://$1" "docker://harbor.wuxing.local/$2" >> ~/lh-prio.log 2>&1; then
    echo "OK $2"
  else
    echo "FAIL $2"
  fi
}
copy docker.io/longhornio/support-bundle-kit:v0.0.56 longhorn/support-bundle-kit:v0.0.56
copy docker.io/longhornio/csi-attacher:v4.9.0 longhorn/csi-attacher:v4.9.0
copy docker.io/longhornio/csi-provisioner:v5.3.0 longhorn/csi-provisioner:v5.3.0
copy docker.io/longhornio/csi-node-driver-registrar:v2.14.0 longhorn/csi-node-driver-registrar:v2.14.0
copy docker.io/longhornio/csi-resizer:v1.13.2 longhorn/csi-resizer:v1.13.2
copy docker.io/longhornio/csi-snapshotter:v8.2.0 longhorn/csi-snapshotter:v8.2.0
copy docker.io/longhornio/livenessprobe:v2.16.0 longhorn/livenessprobe:v2.16.0
copy registry.k8s.io/sig-storage/snapshot-controller:v8.0.1 longhorn/snapshot-controller:v8.0.1
echo PRIO-DONE
