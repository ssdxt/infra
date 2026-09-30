#!/bin/bash
set -u
export NO_PROXY='harbor.wuxing.local,10.100.10.29,localhost,127.0.0.1'
export no_proxy="$NO_PROXY"
H=harbor.wuxing.local; USER=admin; PASS='<HARBOR_PASSWORD>'
OK=0; BAD=0
for t in $(grep -oE '^[a-z0-9./_-]+:[^|]+\|[^ ]+$' ~/mirror.sh | awk -F'|' '{print $2}'); do
  if skopeo inspect --tls-verify=false --creds "$USER:$PASS" "docker://$H/$t" >/dev/null 2>&1; then
    echo "OK    $t"; OK=$((OK+1))
  else
    echo "MISS  $t"; BAD=$((BAD+1))
  fi
done
echo "=== Harbor 校验: 存在 $OK 缺失 $BAD ==="
