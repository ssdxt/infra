#!/bin/bash
set -euo pipefail
export KUBECONFIG=/etc/kubernetes/admin.conf
TS=$(date +%Y%m%d-%H%M%S)
BK=/data1/ssdxt/values/backup/$TS
mkdir -p $BK /data1/ssdxt/values
echo "== backup to $BK =="
helm -n kube-system get values cilium -a -o yaml > $BK/cilium-values-before-unified.yaml
helm -n kube-system get cilium -n kube-system > $BK/helm-full-release.yaml
kubectl -n kube-system get ds,deploy,svc,cm -l app.kubernetes.io/part-of=cilium -o yaml > $BK/cilium-resources.yaml
kubectl -n kube-system get ciliumnetworkpolicies,ciliumloadbalancerippools,ciliumclusterwidenetworkpolicies -o yaml > $BK/cilium-crd.yaml 2>/dev/null || true
kubectl -n gateway get svc cilium-gateway-monitoring-gateway -o yaml > $BK/gateway-svc.yaml
ls -la $BK

echo "== generate unified values =="
helm -n kube-system get values cilium -a -o yaml > /data1/ssdxt/values/cilium-values-unified.yaml

python3 - <<'PYEOF'
import re
p='/data1/ssdxt/values/cilium-values-unified.yaml'
lines=open(p).read().splitlines()
def find(top):
    for i,l in enumerate(lines):
        if re.match(r'^%s:\s*(#.*)?$'%re.escape(top),l): return i
    return -1
adds=[]
for top in ['encryption','bandwidthManager','egressGateway','bgpControlPlane']:
    i=find(top)
    if top=='encryption':
        if i>=0:
            j=i+1
            while j<len(lines) and (lines[j].startswith(' ') or lines[j].strip()==''): j+=1
            lines[i:j]=['encryption:','  enabled: true','  type: wireguard']
        else:
            adds.append('encryption:\n  enabled: true\n  type: wireguard')
    else:
        if i<0:
            adds.append('%s:\n  enabled: true'%top)
        else:
            blk='\n'.join(lines[i+1:i+8])
            if not re.search(r'^  enabled:',blk,re.M):
                lines.insert(i+1,'  enabled: true')
hdr=[
'# =====================================================================',
'# cilium-values-unified.yaml - Cilium 唯一事实来源（single source of truth）',
'# 生成：2026-09-30，基于 helm get values -a 全量生效值，精确合并四大开关：',
'#   encryption(wireguard) / bandwidthManager / egressGateway / bgpControlPlane',
'# 铁律：任何变更后必须执行：',
'#   helm upgrade cilium /data1/ssdxt/charts/cilium-1.20.1.tgz -n kube-system -f /data1/ssdxt/values/cilium-values-unified.yaml --wait --timeout 15m',
'#   然后重跑回归清单（kk-full/30-网络与CNI/cilium-full-stack.md 回归章节）：',
'#   1) 11 agent Ready + operator 正常  2) 4 项镜像修复在位',
'#   3) hubble-peer svc internalTrafficPolicy=Cluster  4) gateway nodePort 32298/32299',
'#   5) 6 域名 https://xxx.wuxing.local:32298 全通  6) WireGuard/带宽/etcd/监控实证',
'# =====================================================================',
]
out='\n'.join(hdr)+'\n'+'\n'.join(lines)+'\n'
if adds:
    out=out.rstrip('\n')+'\n# --- 本次合并新增开关 ---\n'+'\n'.join(adds)+'\n'
open(p,'w').write(out)
print('unified values written')
PYEOF

echo "== key settings =="
grep -nE '^(encryption|bandwidthManager|egressGateway|bgpControlPlane|kubeProxyReplacement|gatewayAPI|hubble|prometheus):' /data1/ssdxt/values/cilium-values-unified.yaml
grep -nA3 '^encryption:' /data1/ssdxt/values/cilium-values-unified.yaml
echo "== image refs in values =="
grep -nE 'harbor|repository|tag:' /data1/ssdxt/values/cilium-values-unified.yaml | head -30