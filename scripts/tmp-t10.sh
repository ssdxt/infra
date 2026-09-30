#!/bin/bash
# Fix: metrics-server needs system:auth-delegator ClusterRoleBinding (subjectaccessreviews)
set -u
F=/data1/ssdxt/monitoring/01-metrics-server.sh
TS=$(date +%m%d-%H%M%S)

echo "=== [1] backup ==="
cp -a $F $F.bak.$TS && echo "  backup: $F.bak.$TS"

echo "=== [2] add system:auth-delegator ClusterRoleBinding ==="
python3 - <<'PY'
p = '/data1/ssdxt/monitoring/01-metrics-server.sh'
s = open(p, encoding='utf-8').read()
anchor = '---\napiVersion: apiregistration.k8s.io/v1\nkind: APIService'
add = '''---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata: {name: metrics-server:system:auth-delegator}
roleRef: {apiGroup: rbac.authorization.k8s.io, kind: ClusterRole, name: system:auth-delegator}
subjects: [{kind: ServiceAccount, name: metrics-server, namespace: kube-system}]
'''
if 'system:auth-delegator' in s:
    print('  already present, skip')
elif anchor in s:
    open(p, 'w', encoding='utf-8').write(s.replace(anchor, add + anchor, 1))
    print('  inserted auth-delegator binding')
else:
    print('  ANCHOR NOT FOUND - not modified')
PY
echo "  --- verify ---"
grep -n 'auth-delegator' $F

echo ""
echo "=== [3] re-run metrics-server script ==="
export KUBECONFIG=/etc/kubernetes/admin.conf
bash $F 2>&1 | tail -14

echo ""
echo "=== [4] verify binding exists ==="
kubectl get clusterrolebinding metrics-server:system:auth-delegator -o wide

echo ""
echo "=== [5] wait 70s then verify ==="
sleep 70
kubectl -n kube-system get pods -l k8s-app=metrics-server
echo "--- top nodes ---"
kubectl top nodes 2>&1
echo "--- top pods -A head ---"
kubectl top pods -A 2>&1 | head -10
