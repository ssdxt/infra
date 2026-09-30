#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
set -u
echo "########## BACKUPS ##########"
mkdir -p /tmp/gwfix-bak
kubectl get httproute -A -o yaml > /tmp/gwfix-bak/httproutes.bak.yaml
kubectl get gateway -n gateway -o yaml > /tmp/gwfix-bak/gateway.bak.yaml
kubectl get svc -n gateway -o yaml > /tmp/gwfix-bak/gateway-svcs.bak.yaml
ls -l /tmp/gwfix-bak/
echo
echo "########## STEP 1: baseline - is Grafana healthy in-cluster? ##########"
echo -n "ClusterIP grafana 10.233.6.13:80/login -> "
curl -s -o /dev/null -w '%{http_code}\n' --max-time 8 http://10.233.6.13/login || echo "fail"
echo -n "prometheus 10.233.34.221:9090 -> "
curl -s -o /dev/null -w '%{http_code}\n' --max-time 8 http://10.233.34.221:9090/graph || echo "fail"
echo -n "alertmanager 10.233.51.28:9093 -> "
curl -s -o /dev/null -w '%{http_code}\n' --max-time 8 http://10.233.51.28:9093/ || echo "fail"
echo
echo "########## STEP 2: CiliumLoadBalancerIPPool for 10.100.10.251 ##########"
cat > /tmp/gwfix-bak/lbpool.yaml <<'YAML'
apiVersion: cilium.io/v2
kind: CiliumLoadBalancerIPPool
metadata:
  name: cilium-lb-pool
spec:
  cidrs:
  - cidr: 10.100.10.251/32
YAML
kubectl apply -f /tmp/gwfix-bak/lbpool.yaml
kubectl get ciliumloadbalancerippool
echo
echo "########## STEP 3: ReferenceGrant in monitoring ns ##########"
cat > /tmp/gwfix-bak/refgrant.yaml <<'YAML'
apiVersion: gateway.networking.k8s.io/v1beta1
kind: ReferenceGrant
metadata:
  name: allow-gateway-httproutes
  namespace: monitoring
spec:
  from:
  - group: gateway.networking.k8s.io
    kind: HTTPRoute
    namespace: gateway
  to:
  - group: ""
    kind: Service
YAML
kubectl apply -f /tmp/gwfix-bak/refgrant.yaml
kubectl get referencegrant -n monitoring
echo
echo "########## STEP 4: repoint HTTPRoutes to real monitoring Services ##########"
kubectl -n gateway patch httproute grafana-route --type merge -p '{"spec":{"rules":[{"matches":[{"path":{"type":"PathPrefix","value":"/"}}],"backendRefs":[{"group":"","kind":"Service","name":"prometheus-stack-grafana","namespace":"monitoring","port":80,"weight":1}]}]}}'
kubectl -n gateway patch httproute monitoring-routes --type merge -p '{"spec":{"rules":[{"matches":[{"path":{"type":"PathPrefix","value":"/"}}],"backendRefs":[{"group":"","kind":"Service","name":"prometheus-stack-grafana","namespace":"monitoring","port":80,"weight":1}]}]}}'
kubectl -n gateway patch httproute prometheus-route --type merge -p '{"spec":{"rules":[{"matches":[{"path":{"type":"PathPrefix","value":"/"}}],"backendRefs":[{"group":"","kind":"Service","name":"prometheus-stack-kube-prom-prometheus","namespace":"monitoring","port":9090,"weight":1}]}]}}'
kubectl -n gateway patch httproute alertmanager-route --type merge -p '{"spec":{"rules":[{"matches":[{"path":{"type":"PathPrefix","value":"/"}}],"backendRefs":[{"group":"","kind":"Service","name":"prometheus-stack-kube-prom-alertmanager","namespace":"monitoring","port":9093,"weight":1}]}]}}'
echo
echo "########## STEP 5: wait 45s and check ##########"
sleep 45
kubectl get gateway -n gateway
kubectl get httproute -A
echo
echo "--- route conditions ---"
kubectl get httproute -A -o jsonpath='{range .items[*]}{.metadata.name}{"  "}{range .status.parents[*].conditions[*]}{.type}={.status}/{.reason} {end}{"\n"}{end}'
echo
echo "########## STEP 6: curl through Gateway IP 10.100.10.251 ##########"
for h in grafana prometheus alertmanager; do
  echo -n "$h.wuxing.local/login -> "
  curl -s -o /dev/null -w '%{http_code}\n' --max-time 10 -H "Host: $h.wuxing.local" http://10.100.10.251/login
done
echo -n "grafana root / -> "
curl -s -o /dev/null -w '%{http_code}\n' --max-time 10 -H 'Host: grafana.wuxing.local' http://10.100.10.251/
echo
echo "--- grafana redirect target (headers) ---"
curl -s -D - -o /dev/null --max-time 10 -H 'Host: grafana.wuxing.local' http://10.100.10.251/login | head -12
echo
echo "########## STEP 7: cleanup leftover test services ##########"
kubectl delete svc test-lb-static -n default --ignore-not-found
kubectl -n default get svc
