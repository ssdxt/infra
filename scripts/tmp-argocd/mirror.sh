#!/bin/bash
set -e
HARBOR=https://10.100.10.29
AUTH="admin:<HARBOR_PASSWORD>"
export NO_PROXY=harbor.wuxing.local,10.100.10.29
export HTTPS_PROXY=http://127.0.0.1:12450
export HTTP_PROXY=http://127.0.0.1:12450

# 1. create argocd project (idempotent)
code=$(curl -sk --noproxy '*' -o /dev/null -w '%{http_code}' -X POST "$HARBOR/api/v2.0/projects" \
  -u "$AUTH" -H 'Content-Type: application/json' \
  -d '{"project_name":"argocd","public":true}')
echo "create project http_code=$code"

# 2. mirror images (amd64 only)
export NO_PROXY=harbor.wuxing.local,10.100.10.29
for img in \
  quay.io/argoproj/argocd:v3.5.3 \
  public.ecr.aws/docker/library/redis:8.2.3-alpine \
  ghcr.io/dexidp/dex:v2.45.1 ; do
  repo="${img%:*}"; tag="${img##*:}"
  name="$(basename "$repo")"
  case "$repo" in
    *docker/library/*) name="redis";;
  esac
  dest="10.100.10.29/argocd/$name:$tag"
  echo "== $img -> $dest"
  skopeo copy --override-arch amd64 --retry-times 3 \
    --dest-tls-verify=false --dest-creds "$AUTH" \
    "docker://$img" "docker://$dest"
done
echo ALL_DONE
