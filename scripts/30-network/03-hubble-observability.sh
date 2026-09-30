#!/bin/bash
# 03-hubble-observability.sh —— Hubble Relay/UI + cilium/envoy 指标接入 Prometheus（幂等）
# 详见 30-网络与CNI/hubble-observability.md；镜像需已在 Harbor（hubble-relay v1.20.1、hubble-ui[-backend] v0.13.5）
set -e
export KUBECONFIG=/etc/kubernetes/admin.conf
DIR=/data1/ssdxt/gateway

echo "== 1. helm 开启 hubble relay/ui + agent prometheus =="
helm upgrade cilium /data1/ssdxt/charts/cilium-1.20.1.tgz -n kube-system \
  -f /data1/ssdxt/cilium-values-before-hubble.yaml \
  --reuse-values \
  --set hubble.relay.enabled=true \
  --set hubble.ui.enabled=true \
  --set prometheus.enabled=true \
  --set prometheus.port=9962 \
  --set hubble.relay.image.useDigest=false \
  --set hubble.ui.frontend.image.useDigest=false \
  --set hubble.ui.backend.image.useDigest=false \
  --timeout 15m >/dev/null

echo "== 2. 4 项镜像修复（每次 helm upgrade 后必做，见 30-网络与CNI §1） =="
kubectl -n kube-system set image ds/cilium cilium-agent=harbor.wuxing.local/cilium/cilium:v1.20.1 >/dev/null
kubectl -n kube-system get ds cilium -o json | python3 -c "
import json,sys,subprocess
d=json.load(sys.stdin)
spec=d['spec']['template']['spec']; body={}
for ck in ('initContainers','containers'):
    nl=[{'name':c['name'],'image':c['image'].split('@sha256:')[0]}
        for c in spec.get(ck) or [] if '@sha256:' in c.get('image','')]
    if nl: body[ck]=nl
p=json.dumps({'spec':{'template':{'spec':body}}})
subprocess.run(['kubectl','patch','ds','cilium','-n','kube-system','--type','strategic','-p',p],capture_output=True)
print('init-digests patched')"
kubectl -n kube-system set image deploy/cilium-operator cilium-operator=harbor.wuxing.local/cilium/operator:v1.20.1 >/dev/null
kubectl -n kube-system patch deploy cilium-operator --type json \
  -p '[{"op":"replace","path":"/spec/template/spec/containers/0/command/0","value":"cilium-operator"}]' >/dev/null
kubectl -n kube-system set image ds/cilium-envoy \
  cilium-envoy=harbor.wuxing.local/cilium/cilium-envoy:v1.37.5-1786810558-766ccfb37260a43e9d228837aa84ce3faf9f64e7 >/dev/null

echo "== 3. rollout =="
kubectl -n kube-system rollout status ds/cilium --timeout=600s
kubectl -n kube-system rollout status ds/cilium-envoy --timeout=600s
kubectl -n kube-system rollout status deploy/cilium-operator --timeout=300s
kubectl -n kube-system rollout status deploy/hubble-relay --timeout=300s
kubectl -n kube-system rollout status deploy/hubble-ui --timeout=300s

echo "== 4. hubble-peer internalTrafficPolicy 改 Cluster（chart 写死 Local，KPR 下 relay 连不上） =="
kubectl -n kube-system patch svc hubble-peer --type merge -p '{"spec":{"internalTrafficPolicy":"Cluster"}}'
kubectl -n kube-system rollout restart deploy/hubble-relay
kubectl -n kube-system rollout status deploy/hubble-relay --timeout=300s

echo "== 5. nodePort 固定复核（helm 不动 gateway svc，防御性重打） =="
kubectl -n gateway patch svc cilium-gateway-monitoring-gateway --type merge -p \
  '{"spec":{"ports":[{"name":"port-80","port":80,"protocol":"TCP","nodePort":32299},{"name":"port-443","port":443,"protocol":"TCP","nodePort":32298}]}}'

echo "== 6. 指标 svc/ServiceMonitor + hubble UI 域名 =="
kubectl apply -f $DIR/cilium-observability.yaml

echo "== 7. Grafana 面板（sidecar ConfigMap 通道） =="
python3 - "$DIR/cilium-gateway-dashboard.json" <<'EOF'
import json,sys
dash=json.load(open(sys.argv[1]))
cm={"apiVersion":"v1","kind":"ConfigMap","metadata":{"name":"cilium-gateway-dashboard","namespace":"monitoring","labels":{"grafana_dashboard":"1"}},"data":{"cilium-gateway.json":json.dumps(dash)}}
open('/tmp/cilium-gateway-dashboard-cm.json','w').write(json.dumps(cm))
EOF
kubectl apply -f /tmp/cilium-gateway-dashboard-cm.json

echo "== 8. 验证 =="
sleep 15
curl -sk -o /dev/null -w 'https hubble.wuxing.local:32298 -> %{http_code}\n' --resolve hubble.wuxing.local:32298:10.100.10.10 https://hubble.wuxing.local:32298/
curl -s --max-time 5 http://10.100.10.10:9962/metrics -o /dev/null -w 'agent 9962: %{http_code}\n'
curl -s --max-time 5 http://10.100.10.10:9964/metrics -o /dev/null -w 'envoy 9964: %{http_code}\n'
PIP=$(kubectl -n monitoring get svc prometheus-stack-kube-prom-prometheus -o jsonpath='{.spec.clusterIP}')
curl -sm 10 "http://$PIP:9090/api/v1/targets" -o /tmp/t.json
python3 - <<'EOF'
import json
d=json.load(open('/tmp/t.json'))
found=[t for t in d['data']['activeTargets'] if 'cilium' in t['labels'].get('job','')]
from collections import Counter
print(dict(Counter((t['labels'].get('job'),t['health']) for t in found)))
EOF
curl -sk -o /dev/null -w 'https grafana:32298 -> %{http_code}\n' --resolve grafana.wuxing.local:32298:10.100.10.10 https://grafana.wuxing.local:32298/
echo DONE
