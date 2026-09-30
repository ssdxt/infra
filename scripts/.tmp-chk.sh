#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
kubectl -n kube-system get pods -l app.kubernetes.io/part-of=cilium --no-headers | grep -v "^cilium.*1/1" | head
echo ===
kubectl -n kube-system get events --field-selector type=Warning --sort-by=.lastTimestamp 2>/dev/null | grep -iE 'pull|image|fail' | tail -8
echo === deploy/ds status ===
kubectl -n kube-system get ds cilium cilium-envoy deploy/cilium-operator deploy/hubble-relay 2>/dev/null
helm -n kube-system history cilium | tail -3