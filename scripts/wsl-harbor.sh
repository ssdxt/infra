#!/bin/bash
H=harbor.wuxing.local
HU=admin
HP=<HARBOR_PASSWORD>
echo "== 测试 harbor api"
curl -sk -o /dev/null -w 'auth=%{http_code}\n' -u $HU:$HP "https://$H/api/v2.0/health"
for p in monitoring cert-manager gateway; do
  echo "== create project $p"
  curl -sk -w 'http=%{http_code}\n' -u $HU:$HP -H 'Content-Type: application/json' -X POST "https://$H/api/v2.0/projects" -d "{\"project_name\":\"$p\",\"public\":true}"
done
echo "== docker login"
echo "$HP" | docker login $H -u $HU --password-stdin 2>&1 | tail -2