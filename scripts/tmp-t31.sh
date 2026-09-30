#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
POD=$(kubectl -n logging get pods -l app.kubernetes.io/name=alloy --no-headers | awk '{print $1}' | head -1)

echo "=== [1] alloy fmt (canonical output proves the file parses) ==="
kubectl -n logging exec $POD -c alloy -- /bin/alloy fmt /tmp/candidate.alloy 2>&1
echo "  fmt-exit=${PIPESTATUS[0]}"

echo ""
echo "=== [2] alloy run in throwaway instance (proves components/attrs are valid) ==="
kubectl -n logging exec $POD -c alloy -- sh -c 'timeout 15 /bin/alloy run --server.http.listen-addr=127.0.0.1:12399 --storage.path=/tmp/alloy-test-storage /tmp/candidate.alloy' 2>&1 | head -40
echo "  (timeout 124 = ran fine for 15s, other = config error)"
