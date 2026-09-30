#!/bin/bash
set -e
curl -sf -x "$HTTPS_PROXY" -L https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml -o /tmp/argocd-install.yaml
echo "== lines: $(wc -l < /tmp/argocd-install.yaml)"
echo "== images:"
grep 'image:' /tmp/argocd-install.yaml | awk '{print $2}' | sort -u
