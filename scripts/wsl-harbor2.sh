#!/bin/bash
export http_proxy=
export https_proxy=
export HTTP_PROXY=
export HTTPS_PROXY=
export no_proxy='10.100.10.0/24,localhost,127.0.0.1,harbor.wuxing.local'
export NO_PROXY='10.100.10.0/24,localhost,127.0.0.1,harbor.wuxing.local'
H=harbor.wuxing.local
echo "== 直连测试（清代理后）"
curl -sk -o /dev/null -w 'domain=%{http_code}\n' --max-time 8 https://$H
echo "== docker login 直连"
echo '<HARBOR_PASSWORD>' | docker login $H -u admin --password-stdin 2>&1 | tail -1
echo "== 建项目"
for p in monitoring cert-manager gateway; do
  curl -sk -w " $p=%{http_code}\n" -u admin:'<HARBOR_PASSWORD>' -H 'Content-Type: application/json' -X POST "https://$H/api/v2.0/projects" -d "{\"project_name\":\"$p\",\"public\":true}" -o /dev/null
done