#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== 1. generated svc FULL yaml ====="
kubectl get svc -n gateway cilium-gateway-monitoring-gateway -o yaml
echo
echo "===== 2. operator log: how address was decided ====="
for p in $(kubectl -n kube-system get pod -o name | grep cilium-operator); do kubectl -n kube-system logs $p --tail=500 2>&1 | grep -iE '10.100.10.251|address|lb.?ipam|pool' | tail -25; done
echo
echo "===== 3. ipvsadm -Ln | grep 251 ====="
ipvsadm -Ln 2>&1 | grep -B2 -A4 '10.100.10.251' || echo "(no ipvs entry for 251)"
echo
echo "===== 4. does kube-vip react to status.loadBalancer.ingress? ====="
kubectl delete svc status-test -n default --ignore-not-found >/dev/null 2>&1
kubectl create svc loadbalancer status-test --tcp=80:80 --dry-run=client -o yaml | kubectl apply -f - >/dev/null
sleep 3
echo "--- manually set status.loadBalancer.ingress = 10.100.10.254 (status subresource) ---"
cat <<'JSON' > /tmp/st.json
{"status":{"loadBalancer":{"ingress":[{"ip":"10.100.10.254","ipMode":"VIP"}]}}}
JSON
kubectl patch svc status-test -n default --subresource=status --type=merge --patch-file /tmp/st.json
sleep 15
echo "--- kube-vip log for 254 ---"
for p in $(kubectl -n kube-system get pod -o name | grep kube-vip); do kubectl -n kube-system logs $p --tail=25 2>&1 | grep -E '254|status-test' ; done
echo "--- ip addr for 254 ---"
ip -o addr show | grep 10.100.10.254 || echo "(254 NOT on any interface -> kube-vip ignores status)"
kubectl delete svc status-test -n default --ignore-not-found >/dev/null 2>&1
echo
echo "===== 5. Envoy clusters/endpoints for gateway/grafana:80 ====="
EP=$(kubectl -n kube-system get pod -o name | grep cilium-envoy | head -1)
echo "envoy pod: $EP"
kubectl -n kube-system exec $EP -- curl -s --max-time 5 http://localhost:9901/clusters 2>&1 | grep -A6 'gateway/grafana' | head -30 || echo "(curl unavailable in envoy pod)"
echo "--- fallback: cilium-dbg envoy admin ---"
kubectl -n kube-system exec cilium-88lxj -c cilium-agent -- cilium-dbg envoy admin clusters 2>&1 | grep -A6 'gateway/grafana' | head -30 || true
echo
echo "===== 6. endpoint slices in gateway ns ====="
kubectl -n gateway get endpointslice -o wide 2>&1
echo
echo "===== 7. namespaces (longhorn?) ====="
kubectl get ns
echo
echo "===== 8. referencegrant CRD ====="
kubectl get crd | grep -i referencegrant
echo
echo "===== 9. monitoring pod ips (grafana/prom/alert) ====="
kubectl -n monitoring get pod -o wide | grep -E 'NAME|grafana|prometheus-|alertmanager-'
