#!/bin/bash
# apply priorityclasses + PDBs (idempotent). 幂等：kubectl apply 可重跑。
# 前置检查：同 ns 已有覆盖同 selector 的 PDB 则不建（当前除 longhorn-system 外无任何用户 PDB）。
export KUBECONFIG=/etc/kubernetes/admin.conf
F=/data1/ssdxt/security/priority-pdb.yaml
[ -f "$F" ] || { echo "missing $F"; exit 1; }
echo "== existing PDBs (excluding longhorn-system) =="
kubectl get pdb -A | grep -v longhorn-system | grep -v '^NAMESPACE' || echo none
echo "== apply =="
kubectl apply -f "$F"
echo "== RESULT =="
kubectl get priorityclass | grep -E 'wxq|NAME'
kubectl get pdb -A | grep -v longhorn-system
