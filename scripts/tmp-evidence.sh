#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== gateway conditions (raw) ==="
kubectl get gateway -n gateway monitoring-gateway -o jsonpath='{.status}' | python3 -m json.tool
echo
echo "=== HTTPRoute backendRefs BEFORE (from backup) vs AFTER ==="
echo "--- BEFORE ---"
python3 - <<'PY'
import yaml
d=yaml.safe_load(open('/tmp/gwfix-bak/httproutes.bak.yaml'))
for r in d['items']:
    for rule in r['spec'].get('rules',[]):
        for b in rule.get('backendRefs',[]):
            print(f"  {r['metadata']['name']}: ns={b.get('namespace','(same)')} svc={b['name']} port={b['port']}")
PY
echo "--- AFTER ---"
kubectl get httproute -n gateway -o json | python3 -c "
import json,sys
d=json.load(sys.stdin)
for r in d['items']:
    for rule in r['spec'].get('rules',[]):
        for b in rule.get('backendRefs',[]):
            print(f\"  {r['metadata']['name']}: ns={b.get('namespace','(same)')} svc={b['name']} port={b['port']}\")
"
echo
echo "=== kube-vip manifest: UNCHANGED (svc_enable + timers) ==="
ls -l /etc/kubernetes/manifests/kube-vip.yaml
grep -A1 -E 'svc_enable|lb_enable|vip_leaseduration|vip_renewdeadline|vip_retryperiod' /etc/kubernetes/manifests/kube-vip.yaml
echo
echo "=== cilium version / helm release untouched ==="
kubectl -n kube-system get ds cilium -o jsonpath='{.spec.template.spec.containers[0].image}'; echo
kubectl -n kube-system get cm cilium-config -o jsonpath='{.data.enable-gateway-api}{" / lb-ipam="}{.data.enable-lb-ipam}{" / default-ipam="}{.data.default-lb-service-ipam}'; echo
echo
echo "=== objects created by this fix ==="
kubectl get ciliumloadbalancerippool cilium-lb-pool -o name
kubectl get referencegrant -n monitoring allow-gateway-httproutes -o name
echo
echo "=== longhorn namespace check (why longhorn route 503) ==="
kubectl get ns longhorn-system 2>&1
kubectl get svc -n gateway longhorn -o jsonpath='{.spec.externalName}'; echo
echo
echo "=== gateway ns final services ==="
kubectl -n gateway get svc
echo
echo "=== FINAL gateway line ==="
kubectl get gateway -n gateway
echo "=== FINAL required curl ==="
IP=$(kubectl get gateway -n gateway monitoring-gateway -o jsonpath='{.status.addresses[0].value}')
echo "curl -s -o /dev/null -w '%{http_code}' -H 'Host: grafana.wuxing.local' http://$IP/login"
curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: grafana.wuxing.local' http://$IP/login
