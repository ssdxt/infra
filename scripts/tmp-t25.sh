#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "############ A. long-running API requests by resource (pods/log = Alloy's mode) ############"
kubectl get --raw='/metrics' 2>/dev/null | grep '^apiserver_longrunning_requests{' | sort -t'}' -k2 -rn | head -12
echo "--- count of pods/log streams ---"
kubectl get --raw='/metrics' 2>/dev/null | grep '^apiserver_longrunning_requests{' | grep 'resource="pods"' | head -5

echo ""
echo "############ B. request rate by verb/resource (top) ############"
kubectl get --raw='/metrics' 2>/dev/null | grep -E '^apiserver_request_total\{' | grep -vE 'verb="(WATCH|GET)"' | sort -t' ' -k2 -rn | head -8

echo ""
echo "############ C. alloy chart: host mounts support ############"
helm -n logging show values alloy 2>/dev/null | grep -n -A18 '^alloy:' | head -40
echo "--- mounts key ---"
helm -n logging show values alloy 2>/dev/null | grep -n -B2 -A12 'mounts:' | head -30

echo ""
echo "############ D. current alloy pod volume mounts (live) ############"
kubectl -n logging get ds alloy -o yaml 2>/dev/null | sed -n '/volumeMounts:/,/dnsPolicy/p' | head -20
