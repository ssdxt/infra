#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== cilium-59g4t images ==="
kubectl -n kube-system get pod cilium-59g4t -o json | python3 -c "
import json,sys
d=json.load(sys.stdin)
for c in d['spec'].get('initContainers',[])+d['spec'].get('containers',[]):
    print(c['name'],'=',c['image'])"
echo "=== envoy-6rmfk ==="
kubectl -n kube-system get pod cilium-envoy-6rmfk -o jsonpath='{.spec.containers[0].image}'; echo
echo "=== operator ==="
kubectl -n kube-system get deploy cilium-operator -o json | python3 -c "
import json,sys
d=json.load(sys.stdin)
c=d['spec']['template']['spec']['containers'][0]
print('image =',c['image']); print('command =',c.get('command'))"
echo "=== events ==="
kubectl -n kube-system get events --field-selector type=Warning --sort-by=.lastTimestamp 2>/dev/null | grep -iE 'pull|image' | tail -10