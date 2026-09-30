#!/bin/bash
# otel operator smoke: retry until stable window, then create smoke collector
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=opentelemetry-operator-system
for i in 1 2 3 4 5 6 7 8 9 10; do
  kubectl -n $NS delete po -l app.kubernetes.io/name=opentelemetry-operator --force --grace-period=0 2>/dev/null
  if kubectl -n $NS rollout status deploy/opentelemetry-operator --timeout=150s 2>/dev/null; then
    echo "== operator ready on attempt $i"
    break
  fi
  echo "== attempt $i failed, retrying"
  sleep 5
done
kubectl -n $NS get po -o wide
kubectl apply -f /data1/ssdxt/otel/smoke-collector.yaml
for i in 1 2 3; do
  if kubectl -n $NS rollout status deploy/smoke-collector --timeout=120s; then break; fi
  kubectl -n $NS delete po -l app.kubernetes.io/name=opentelemetry-operator --force --grace-period=0 2>/dev/null
  sleep 10
done
kubectl get otelcol,po -n $NS -o wide
echo '== smoke image:'
kubectl get deploy -n $NS smoke-collector -o jsonpath='{.spec.template.spec.containers[0].image}'; echo
echo '== collector startup log:'
kubectl logs -n $NS deploy/smoke-collector --tail=25 2>&1 | head -40
