#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=tetragon
echo "== apply 策略"
kubectl apply -f /data1/ssdxt/security/policies-baseline.yaml
sleep 6
echo "== 加载检查（应无 failed loading 报错）"
POD=$(kubectl -n $NS get pod -l app.kubernetes.io/name=tetragon -o name | head -1)
kubectl -n $NS logs "$POD" -c tetragon --tail=300 2>/dev/null | grep -m4 'shell-exec' || echo "(无相关日志=加载成功无报错)"
echo
echo "== 触发：在 kube-system coredns 里跑 date（exists in image? 用 /bin/date）"
kubectl -n kube-system exec coredns-646f4dc8fb-9fm4x -- /bin/date >/dev/null 2>&1 || \
  kubectl -n kube-system exec "$(kubectl -n kube-system get pod -l k8s-app=kube-proxy -o name | head -1)" -- sh -c 'echo kp-test' >/dev/null 2>&1
sleep 6
echo "== shell-exec-kube-system 事件"
kubectl -n $NS logs -l app.kubernetes.io/name=tetragon -c export-stdout --tail=4000 --prefix 2>/dev/null \
  | grep 'process_kprobe' | grep -m1 'shell-exec-kube-system' | head -c 1000; echo
