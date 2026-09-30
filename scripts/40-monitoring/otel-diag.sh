export KUBECONFIG=/etc/kubernetes/admin.conf
echo '== final state =='
kubectl get po -n opentelemetry-operator-system
kubectl get netpol -n opentelemetry-operator-system 2>/dev/null || echo 'netpol: none'
kubectl get otelcol -A
helm list -n opentelemetry-operator-system
