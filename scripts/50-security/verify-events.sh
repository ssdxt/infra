#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=tetragon
echo "== sensitive-file: /etc/shadow kprobe event"
kubectl -n $NS logs -l app.kubernetes.io/name=tetragon -c export-stdout --tail=8000 --prefix 2>/dev/null \
  | grep -m1 'etc/shadow' | head -c 1800; echo
echo
echo "== process_kprobe event from policies (any)"
kubectl -n $NS logs -l app.kubernetes.io/name=tetragon -c export-stdout --tail=8000 --prefix 2>/dev/null \
  | grep -m2 'process_kprobe' | head -c 2400; echo
echo
echo "== kube-system execve policy event (tetra getevents, node wxq-run-01)"
POD=$(kubectl -n $NS get pod -l app.kubernetes.io/name=tetragon --field-selector spec.nodeName=wxq-control-01 -o name | head -1)
kubectl -n kube-system exec kube-apiserver-wxq-control-01 -- ls / >/dev/null 2>&1 || true
sleep 4
timeout 12 kubectl -n $NS exec "$POD" -c tetragon -- /usr/bin/tetra tracingpolicies list 2>&1 | head -12
