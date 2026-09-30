#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=tetragon
echo "== A) shadow 专用 kprobe 命中（process_kprobe + policy sensitive-file-shadow）"
kubectl -n default run tg-smoke --image=harbor.wuxing.local/library/busybox:1.38.0 --restart=Never --command -- sleep 300 2>/dev/null
kubectl -n default wait --for=condition=Ready pod/tg-smoke --timeout=120s
kubectl -n default exec tg-smoke -- cat /etc/shadow >/dev/null 2>&1
sleep 5
kubectl -n $NS logs -l app.kubernetes.io/name=tetragon -c export-stdout --tail=5000 --prefix 2>/dev/null \
  | grep 'process_kprobe' | grep -m1 'sensitive-file-shadow' | head -c 1200; echo
echo
echo "== B) kube-system execve 观察策略命中"
kubectl -n $NS logs -l app.kubernetes.io/name=tetragon -c export-stdout --tail=5000 --prefix 2>/dev/null \
  | grep 'process_kprobe' | grep -m1 'shell-exec-kube-system' | head -c 1200; echo
echo
echo "== C) tetra cgroup/events 快照"
POD=$(kubectl -n $NS get pod -l app.kubernetes.io/name=tetragon --field-selector spec.nodeName=wxq-run-08 -o name | head -1)
timeout 12 kubectl -n $NS exec "$POD" -c tetragon -- /usr/bin/tetra cgroups list 2>&1 | head -3
kubectl -n default delete pod tg-smoke --ignore-not-found
