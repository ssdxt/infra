#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== kubectl version / nodes ====="
kubectl version --short 2>/dev/null | head -5
kubectl get nodes --no-headers | wc -l
echo
echo "===== prometheus CRD object ====="
kubectl -n monitoring get prometheus prometheus-stack-kube-prom-prometheus -o yaml > /tmp/prom-crd-before.yaml 2>&1
echo "exit=$?"
wc -l /tmp/prom-crd-before.yaml
grep -n -A6 'remoteWrite' /tmp/prom-crd-before.yaml || echo "NO remoteWrite section"
echo
echo "===== prometheus crd: key spec fields ====="
kubectl -n monitoring get prometheus prometheus-stack-kube-prom-prometheus -o jsonpath='{.spec.retention}{"\n"}{.spec.storage}{"\n"}{.spec.replicas}{"\n"}{.spec.version}{"\n"}'
echo
echo "===== pods in monitoring ====="
kubectl -n monitoring get pods -o wide
echo
echo "===== count servicemonitors / prometheusrules ====="
echo -n "servicemonitors: "; kubectl -n monitoring get servicemonitor --no-headers 2>/dev/null | wc -l
echo -n "prometheusrules: "; kubectl -n monitoring get prometheusrule --no-headers 2>/dev/null | wc -l
echo -n "prometheusrules ALL NS: "; kubectl get prometheusrule -A --no-headers 2>/dev/null | wc -l
echo
echo "===== the existing script 02-remote-write.sh ====="
ls -la /data1/ssdxt/monitoring/ 2>&1
echo "--- content:"
cat /data1/ssdxt/monitoring/02-remote-write.sh 2>&1
echo
echo "===== connectivity plant01:9091 from cluster ====="
timeout 8 curl -s -o /dev/null -w 'runtimeinfo_http=%{http_code}\n' http://10.100.10.29:9091/api/v1/status/runtimeinfo 2>&1
timeout 8 curl -s -o /dev/null -w 'write_probe_http=%{http_code}\n' -XPOST 'http://10.100.10.29:9091/api/v1/write' 2>&1
echo
echo "===== plant01 baseline count(up) via cluster ====="
timeout 8 curl -s "http://10.100.10.29:9091/api/v1/query?query=count(up)" 2>&1 | head -c 400
echo
echo "===== current cluster prometheus remote_storage metrics (baseline) ====="
POD=$(kubectl -n monitoring get pods -l app.kubernetes.io/name=prometheus -o name 2>/dev/null | head -1)
echo "POD=$POD"
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/query?query=prometheus_remote_storage_samples_total' 2>&1 | head -c 500
echo
echo "===== targets up count ====="
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/query?query=count(up)' 2>&1 | head -c 400
echo
echo "===== python3 available? ====="
which python3 && python3 -V
