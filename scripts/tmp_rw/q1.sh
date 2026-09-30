#!/bin/sh
P="kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO-"
echo "=== rate failed 5m ==="
$P 'http://localhost:9090/api/v1/query?query=rate(prometheus_remote_storage_samples_failed_total%5B5m%5D)'
echo; echo "=== pending ==="
$P 'http://localhost:9090/api/v1/query?query=prometheus_remote_storage_samples_pending'
echo; echo "=== shards ==="
$P 'http://localhost:9090/api/v1/query?query=prometheus_remote_storage_shards'
echo; echo "=== failed total ==="
$P 'http://localhost:9090/api/v1/query?query=prometheus_remote_storage_samples_failed_total'
echo; echo "=== sent total ==="
$P 'http://localhost:9090/api/v1/query?query=prometheus_remote_storage_samples_total'
echo; echo "=== retry after ==="
$P 'http://localhost:9090/api/v1/query?query=prometheus_remote_storage_succeeded_samples_total'
echo
