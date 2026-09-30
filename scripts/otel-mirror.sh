#!/bin/bash
set -e
export HTTPS_PROXY=http://127.0.0.1:12450
export NO_PROXY=harbor.wuxing.local,10.100.10.29
HC='admin:<HARBOR_PASSWORD>'
H='https://harbor.wuxing.local'

# Harbor 请求不走代理
code=$(env -u HTTPS_PROXY -u HTTP_PROXY -u https_proxy -u http_proxy \
  curl -sk -u "$HC" -X POST "$H/api/v2.0/projects" -H 'Content-Type: application/json' \
  -d '{"project_name":"otel","public":true}' -o /tmp/proj.out -w '%{http_code}')
echo "create project http=$code"; cat /tmp/proj.out; echo

copy() {
  src=$1; dst=$2
  echo "== $src -> $dst"
  skopeo copy --override-arch amd64 --retry-times 3 \
    --dest-tls-verify=false --dest-creds "$HC" "docker://$src" "docker://$dst" || { echo FAILED; exit 1; }
}
B='harbor.wuxing.local/otel'
copy ghcr.io/open-telemetry/opentelemetry-operator/opentelemetry-operator:0.159.0 $B/opentelemetry-operator:0.159.0
copy ghcr.io/open-telemetry/opentelemetry-collector-releases/opentelemetry-collector-k8s:0.159.0 $B/opentelemetry-collector-k8s:0.159.0
copy ghcr.io/open-telemetry/opentelemetry-collector-releases/opentelemetry-collector:0.159.0 $B/opentelemetry-collector:0.159.0
echo ALL_DONE
