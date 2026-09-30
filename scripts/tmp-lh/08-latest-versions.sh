#!/bin/bash
export HTTPS_PROXY=http://127.0.0.1:12450
helm repo update longhorn >/dev/null 2>&1
helm search repo longhorn/longhorn --versions -o json | python3 -c "
import json,sys
vs=[(v['app_version'],v['version']) for v in json.load(sys.stdin)]
seen={}
for app,chart in vs:
    minor='.'.join(app.split('.')[:2])
    if minor not in seen: seen[minor]=(app,chart)
for m in sorted(seen): print(m, seen[m])
" | head -20
