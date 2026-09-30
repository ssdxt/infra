#!/bin/bash
set -e
export KUBECONFIG=/etc/kubernetes/admin.conf
V=/data1/ssdxt/values/cilium-values-unified.yaml
sed -i 's/useDigest: true/useDigest: false/g' $V
python3 - <<'PYEOF'
p='/data1/ssdxt/values/cilium-values-unified.yaml'
t=open(p).read()
t=t.replace('    override: null\n    pullPolicy: IfNotPresent\n    repository: harbor.wuxing.local/cilium/operator',
            '    override: harbor.wuxing.local/cilium/operator:v1.20.1\n    pullPolicy: IfNotPresent\n    repository: harbor.wuxing.local/cilium/operator')
open(p,'w').write(t)
PYEOF
grep -c "useDigest: false" $V
grep -n "override: harbor" $V
echo "== helm upgrade retry =="
helm upgrade cilium /data1/ssdxt/charts/cilium-1.20.1.tgz -n kube-system -f $V --wait --timeout 15m 2>&1 | tail -8