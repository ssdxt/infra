#!/bin/bash
helm show values /data1/ssdxt/charts/alloy-0.12.0.tgz 2>/dev/null | python3 -c "
import sys,yaml
v=yaml.safe_load(sys.stdin)
a=v.get('alloy',{})
print('alloy.* keys:', list(a.keys()))
print('alloy.mounts =', a.get('mounts'))
print('top-level keys:', list(v.keys()))
"