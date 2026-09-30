#!/bin/bash
set -x
export HTTPS_PROXY=http://127.0.0.1:12450
export NO_PROXY=harbor.wuxing.local,10.100.10.29
skopeo list-tags docker://docker.io/curlimages/curl 2>/dev/null | python3 -c 'import json,sys;ts=json.load(sys.stdin)["Tags"];print([t for t in ts if t.startswith("8.")][-5:])'
skopeo copy --override-arch amd64 --retry-times 3 \
  --dest-tls-verify=false --dest-creds admin:<HARBOR_PASSWORD> \
  docker://docker.io/curlimages/curl:8.16.0 \
  docker://harbor.wuxing.local/library/curl:8.16.0 \
  && echo OK curl:8.16.0
