#!/bin/bash
set -x
export HTTPS_PROXY=http://127.0.0.1:12450
export NO_PROXY=harbor.wuxing.local,10.100.10.29
skopeo copy --override-arch amd64 --retry-times 3 \
  --dest-tls-verify=false --dest-creds admin:<HARBOR_PASSWORD> \
  docker://reg.kyverno.io/kyverno/kyverno-cli:v1.19.1 \
  docker://harbor.wuxing.local/kyverno/kyverno-cli:v1.19.1 && echo OK
