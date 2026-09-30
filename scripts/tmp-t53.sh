#!/bin/bash
# DIAGNOSE ONLY (no changes): why are etcd metrics 0 series in Prometheus?
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=monitoring

echo "############ A. ServiceMonitors referencing etcd ############"
kubectl -n $NS get servicemonitor 2>&1 | grep -i etcd || echo "  none found by name"
echo "  --- the etcd ServiceMonitor spec ---"
kubectl -n $NS get servicemonitor -o json 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)
for i in d['items']:
    if 'etcd' in i['metadata']['name']:
        print('  name:', i['metadata']['name'])
        print('  labels:', i['metadata'].get('labels'))
        print('  selector:', i['spec'].get('selector'))
        print('  endpoints:'); print(json.dumps(i['spec'].get('endpoints'),indent=3,ensure_ascii=False))
        print('  namespaceSelector:', i['spec'].get('namespaceSelector'))
        print('  jobLabel:', i['spec'].get('jobLabel'))
"

echo ""
echo "############ B. does Prometheus actually have an etcd scrape config job? ############"
kubectl -n $NS exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/status/config' 2>/dev/null | python3 -c "
import sys,json,yaml
d=json.load(sys.stdin)['data']['yaml']
cfg=yaml.safe_load(d)
for sc in cfg.get('scrape_configs',[]):
    if 'etcd' in sc.get('job_name','').lower():
        print('  job found:', sc.get('job_name'))
        for st in sc.get('static_configs',[]): print('    static:', st)
        print('    scheme:', sc.get('scheme'), ' metrics_path:', sc.get('metrics_path'))
        print('    tls_config:', sc.get('tls_config'))
        print('    basic_auth:', sc.get('basic_auth'))
print('  total jobs:', len(cfg.get('scrape_configs',[])))
print('  jobs:', [s['job_name'] for s in cfg.get('scrape_configs',[])])
"

echo ""
echo "############ C. Prometheus TARGETS for etcd: health + lastError ############"
kubectl -n $NS exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/targets' 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']
allt=d.get('activeTargets',[])+d.get('droppedTargets',[])
found=False
for t in allt:
    lbl=t.get('labels',{}) or t.get('discoveredLabels',{})
    if 'etcd' in json.dumps(lbl).lower():
        found=True
        print('  labels:', {k:v for k,v in (t.get('labels') or {}).items() if k in ('job','instance','namespace','endpoint')})
        print('   scrapeUrl:', t.get('scrapeUrl'))
        print('   health:', t.get('health'), ' lastError:', (t.get('lastError') or '')[:300])
        print('   lastScrape:', t.get('lastScrape'))
if not found: print('  NO etcd target at all (neither active nor dropped)')
print('  active targets:', len(d.get('activeTargets',[])), ' dropped:', len(d.get('droppedTargets',[])))
"

echo ""
echo "############ D. Service / Endpoints for etcd ############"
kubectl -n kube-system get svc -o wide 2>&1 | grep -i etcd || echo "  no etcd Service in kube-system"
echo "  --- any etcd service anywhere ---"
kubectl get svc -A 2>&1 | grep -i etcd || echo "  NONE - no etcd Service exists"
echo "  --- etcd EndpointSlices referencing kube-etcd ---"
kubectl get endpointslice -A 2>&1 | grep -i etcd || echo "  none"

echo ""
echo "############ E. is etcd actually listening, and on which IP/port? ############"
for ip in 10.100.10.10 10.100.10.14 10.100.10.19; do
  echo "  --- $ip ---"
  ssh -o BatchMode=yes -o ConnectTimeout=6 root@$ip "ss -tlnp 2>/dev/null | grep -E ':(2379|2380|2381)' | sed 's/^/     /'" 2>&1
done
echo "  --- etcd static pod manifest: listen + cert flags ---"
for ip in 10.100.10.10; do
  ssh -o BatchMode=yes -o ConnectTimeout=6 root@$ip "grep -oE '\-\-(listen-[a-z-]+|advertise-client-urls|cert-file|key-file|trusted-ca-file|client-cert-auth|peer-[a-z-]+)=[^ ]*' /etc/kubernetes/manifests/etcd.yaml 2>/dev/null | sed 's/^/     /'" 2>&1
done

echo ""
echo "############ F. does the etcd client cert secret exist (as the SM expects)? ############"
kubectl -n $NS get secrets 2>&1 | grep -iE 'etcd|kube-etcd' || echo "  no etcd-related secret in monitoring ns"
kubectl -n kube-system get secrets 2>&1 | grep -iE 'etcd' || echo "  no etcd secret in kube-system"
echo "  --- kube-prometheus-stack chart values: etcd section (was it enabled?) ---"
helm -n $NS get values prometheus-stack 2>/dev/null | grep -i -A12 'etcd' | head -40

echo ""
echo "############ G. can Prometheus reach the etcd IPs at all? (from inside prometheus pod) ############"
POD=prometheus-prometheus-stack-kube-prom-prometheus-0
for ip in 10.100.10.10 10.100.10.14 10.100.10.19; do
  r=$(kubectl -n $NS exec $POD -c prometheus -- sh -c "wget -qO- --timeout=5 --no-check-certificate https://$ip:2379/health 2>&1 | head -c 120" 2>&1)
  echo "  $ip:2379 -> ${r:-<empty>}"
done
