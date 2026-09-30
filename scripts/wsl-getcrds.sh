#!/bin/bash
# Download external-snapshotter v8.0.1 CRDs (Longhorn 1.7.2 uses csi-snapshotter v7.0.2 <-> external-snapshotter v8.0)
set -u
D=/tmp/dsh-crds
mkdir -p $D && cd $D
V=v8.0.1
BASE=https://raw.githubusercontent.com/kubernetes-csi/external-snapshotter/$V/client/config/crd
for f in snapshot.storage.k8s.io_volumesnapshotclasses.yaml \
         snapshot.storage.k8s.io_volumesnapshotcontents.yaml \
         snapshot.storage.k8s.io_volumesnapshots.yaml; do
  echo -n "download $f ... "
  curl -sSL --max-time 60 -o $D/$f $BASE/$f && echo "OK ($(wc -c < $D/$f) bytes)" || echo FAIL
done
echo "--- sanity: kind/CRD names ---"
grep -h -E '^  name: .*snapshot.storage.k8s.io' $D/*.yaml
echo "--- copy to windows path ---"
mkdir -p /mnt/c/Users/CC/Desktop/dsh/crds
cp $D/*.yaml /mnt/c/Users/CC/Desktop/dsh/crds/
ls -la /mnt/c/Users/CC/Desktop/dsh/crds/
