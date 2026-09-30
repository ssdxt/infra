#!/bin/bash
for v in 1.8.2 1.11.3 1.12.1 1.13.0; do
  echo "== $v"
  grep -il 'snapshot-controller' /tmp/render-$v.yaml || echo "  no snapshot-controller"
  grep -oE 'name: csi-snapshotter|name: csi-provisioner|name: csi-attacher|name: csi-resizer' /tmp/render-$v.yaml | sort -u
done
