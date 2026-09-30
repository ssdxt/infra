#!/bin/bash
# Mirror kyverno v1.19.1 images (amd64) into Harbor kyverno/ project（幂等，重跑只更新 tag）
set -x
HARBOR=harbor.wuxing.local
CREDS=admin:<HARBOR_PASSWORD>
V=v1.19.1

# 1. ensure project exists (201 created / 409 exists) —— Harbor 直连，先去掉代理
unset HTTPS_PROXY https_proxy HTTP_PROXY http_proxy NO_PROXY no_proxy
code=$(curl -sk -u "$CREDS" -X POST "https://$HARBOR/api/v2.0/projects" \
  -H 'Content-Type: application/json' \
  -d '{"project_name":"kyverno","public":false}' \
  -o /dev/null -w '%{http_code}')
echo "create project: $code"

# 2. mirror images (explicit tags only, amd64, no digest) —— 源拉取需要代理
export NO_PROXY=harbor.wuxing.local,10.100.10.29
copy() { # $1=source image (no tag)  $2=tag  $3=dest repo (under kyverno/)
  export HTTPS_PROXY=http://127.0.0.1:12450
  skopeo copy --override-arch amd64 --retry-times 3 \
    --dest-tls-verify=false --dest-creds "$CREDS" \
    "docker://$1:$2" "docker://$HARBOR/kyverno/$3:$2" \
    && echo "OK $3:$2" || echo "FAIL $3:$2"
}
copy reg.kyverno.io/kyverno/kyverno             $V kyverno
copy reg.kyverno.io/kyverno/kyvernopre          $V kyvernopre
copy reg.kyverno.io/kyverno/cleanup-controller  $V cleanup-controller
copy reg.kyverno.io/kyverno/kyverno-cli         $V kyverno-cli   # helm post-upgrade migrate hook 用
copy ghcr.io/kyverno/readiness-checker          $V readiness-checker
unset HTTPS_PROXY https_proxy

# 3. verify via Harbor API (docker registry /v2 tags/list 需 token，改用 v2.0 API)
for r in kyverno kyvernopre cleanup-controller readiness-checker; do
  echo "== $r =="
  curl -sk -u "$CREDS" "https://$HARBOR/api/v2.0/projects/kyverno/repositories/$r/artifacts?with_tag=true" \
    | grep -o '"name":"v1.19.1"'
done
