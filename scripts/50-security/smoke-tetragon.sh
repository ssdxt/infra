#!/bin/bash
# Tetragon 冒烟验证：触发事件并抓取 JSON 证据
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=tetragon
IMG=harbor.wuxing.local/library/busybox:1.38.0

echo "== 1) 组件状态"
kubectl -n $NS get pods

echo "== 2) 通用进程事件冒烟：default ns busybox 执行 ls /"
kubectl -n default delete pod tg-smoke --ignore-not-found
kubectl -n default run tg-smoke --image="$IMG" --restart=Never --command -- sleep 300
kubectl -n default wait --for=condition=Ready pod/tg-smoke --timeout=120s
kubectl -n default exec tg-smoke -- ls / >/dev/null
sleep 5

echo "== 3) tetragon 日志中查找 tg-smoke 进程事件"
kubectl -n $NS logs -l app.kubernetes.io/name=tetragon -c tetragon --tail=5000 --prefix 2>/dev/null | grep -m3 'tg-smoke'

echo "== 4) 敏感文件策略冒烟：读 /etc/shadow"
kubectl -n default exec tg-smoke -- cat /etc/shadow >/dev/null 2>&1
sleep 5
kubectl -n $NS logs -l app.kubernetes.io/name=tetragon -c tetragon --tail=8000 --prefix 2>/dev/null | grep -m2 'etc/shadow'

echo "== 5) tetra CLI/GRPC 直读事件流（不经 export 过滤）"
POD=$(kubectl -n $NS get pod -l app.kubernetes.io/name=tetragon --field-selector spec.nodeName=wxq-run-08 -o name | head -1)
echo "pod: $POD"
kubectl -n default exec tg-smoke -- sh -c 'echo hello-from-shell' >/dev/null
sleep 3
timeout 15 kubectl -n $NS exec "$POD" -c tetragon -- /usr/bin/tetra getevents -o compact --namespaces default 2>&1 | tail -5 || echo "(tetra getevents timed out as expected; see export logs above)"

kubectl -n default delete pod tg-smoke --ignore-not-found
echo "== done"
