#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== FULL Prometheus CRD spec (before) ====="
kubectl -n monitoring get prometheus prometheus-stack-kube-prom-prometheus -o yaml
echo
echo "===== cluster-wide servicemonitor / prometheusrule counts ====="
echo -n "SM all ns: "; kubectl get servicemonitor -A --no-headers 2>/dev/null | wc -l
echo -n "PR all ns: "; kubectl get prometheusrule -A --no-headers 2>/dev/null | wc -l
echo "--- PR list:"
kubectl get prometheusrule -A --no-headers 2>/dev/null
echo
echo "===== podmonitor count ====="
kubectl get podmonitor -A --no-headers 2>/dev/null | wc -l
echo
echo "===== job names scraped by cluster prometheus ====="
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/label/job/values' 2>&1
echo
echo "===== cluster prometheus externalLabels + config ====="
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/status/config' 2>&1 | head -c 300
echo
echo "===== rule count / alerts ====="
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/rules?type=alert' 2>&1 | grep -o '"name":"[^"]*"' | wc -l
echo
echo "===== kube-state-metrics restarts (pre-existing issue check) ====="
kubectl -n monitoring get pod -l app.kubernetes.io/name=kube-state-metrics -o jsonpath='{range .items[*]}{.metadata.name} restarts={.status.containerStatuses[0].restartCount} lastState={.status.containerStatuses[0].lastState}{"\n"}{end}'
echo
echo "===== does cluster prometheus have PVC? ====="
kubectl -n monitoring get pvc
