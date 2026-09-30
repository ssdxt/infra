#!/bin/sh
echo "=== remote write errors (cluster prom) ==="
kubectl -n monitoring logs prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus --tail=300 2>&1 | grep -iE 'remote|write|error' | tail -40
