#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=tetragon
POD=$(kubectl -n $NS get pod -l app.kubernetes.io/name=tetragon -o name | head -1)
test_variant() {
  local name=$1 call=$2
  cat <<EOF | kubectl apply -f - >/dev/null
apiVersion: cilium.io/v1alpha1
kind: TracingPolicyNamespaced
metadata:
  name: tp-test-$name
  namespace: default
spec:
  kprobes:
  - call: "$call"
    syscall: true
    args:
    - index: 0
      type: "char_buf"
      sizeArgIndex: 1
EOF
  sleep 4
  echo "-- variant $name ($call):"
  kubectl -n $NS logs "$POD" -c tetragon --since=20s 2>/dev/null | grep -m1 "tp-test-$name" | head -c 400
  echo
  kubectl delete tracingpoliciesnamespaced.cilium.io -n default tp-test-$name --ignore-not-found >/dev/null
}
test_variant a "sys_execve"
test_variant b "execve"
