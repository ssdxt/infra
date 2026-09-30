#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== containerd config registry section ==="
grep -n -A6 -i 'registry\|harbor' /etc/containerd/config.toml | head -60
echo "=== certs.d tree ==="
find /etc/containerd -maxdepth 4 -name '*.crt' -o -maxdepth 4 -type d -name 'certs.d' 2>/dev/null
ls -R /etc/containerd/certs.d 2>&1 | head -20
echo "=== images used by running pods (unique repos) ==="
kubectl get pods -A -o jsonpath='{range .items[*]}{.spec.containers[*].image}{"\n"}{end}' | tr ' ' '\n' | sed 's#/.*##' | sort -u
echo "=== sample images ==="
kubectl get pods -A -o jsonpath='{range .items[*]}{.spec.containers[0].image}{"\n"}{end}' | sort -u | head -20
echo "=== CA files ==="
ls -la /usr/local/share/ca-certificates/ 2>&1