#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=tetragon
echo "== tetragon 日志中 shell-exec 策略加载情况"
kubectl -n $NS logs -l app.kubernetes.io/name=tetragon -c tetragon --tail=500 --prefix 2>/dev/null | grep -m4 'shell-exec'
echo
echo "== 触发：在 coredns pod 里执行 sh"
POD=$(kubectl -n kube-system get pod -l k8s-app=kube-dns -o name | head -1)
echo "target: $POD"
kubectl -n kube-system exec "$POD" -- ls /etc >/dev/null 2>&1 || echo "(exec failed)"
sleep 6
echo "== 找 kube-system 中的 execve 事件"
kubectl -n $NS logs -l app.kubernetes.io/name=tetragon -c export-stdout --tail=6000 --prefix 2>/dev/null \
  | grep 'process_kprobe' | grep 'kube-system' | tail -2 | head -c 2000; echo
echo
echo "== 该策略有没有报错"
kubectl get tracingpoliciesnamespaced.cilium.io -n kube-system shell-exec-kube-system -o jsonpath='{.status}'; echo
