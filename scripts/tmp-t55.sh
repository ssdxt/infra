#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "############ A. is etcd a systemd service (not a static pod)? ############"
for ip in 10.100.10.10; do
  echo "  --- $ip ---"
  ssh -o BatchMode=yes -o ConnectTimeout=6 root@$ip "systemctl is-active etcd 2>&1; systemctl is-enabled etcd 2>&1; echo '--- unit ---'; systemctl cat etcd 2>&1 | head -30" 2>&1 | sed 's/^/   /'
done

echo ""
echo "############ B. actual etcd process + flags ############"
ssh -o BatchMode=yes -o ConnectTimeout=6 root@10.100.10.10 "ps -eo pid,args | grep -E '[e]tcd' | head -3" 2>&1 | sed 's/^/   /'
echo "  --- flags split one per line ---"
ssh -o BatchMode=yes -o ConnectTimeout=6 root@10.100.10.10 "ps -eo args | grep -E '^/usr/local/bin/etcd|[e]tcd ' | head -1 | tr ' ' '\n' | grep -E 'listen|url|cert|auth|name=|data-dir' | sed 's/^/     /'" 2>&1

echo ""
echo "############ C. what is in /etc/kubernetes/manifests ? ############"
ssh -o BatchMode=yes -o ConnectTimeout=6 root@10.100.10.10 "ls -la /etc/kubernetes/manifests/ 2>&1" | sed 's/^/   /'
echo "  --- where are etcd certs? ---"
ssh -o BatchMode=yes -o ConnectTimeout=6 root@10.100.10.10 "ls -la /etc/kubernetes/pki/etcd/ 2>&1; echo '--- /etc/etcd ---'; ls -la /etc/etcd/ /etc/etcd/pki 2>&1 | head -20" | sed 's/^/   /'

echo ""
echo "############ D. EndpointSlice for the etcd Service (as JSON) ############"
kubectl -n kube-system get endpointslice -o json 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)
hit=False
for i in d['items']:
    if 'etcd' in i['metadata']['name']:
        hit=True
        print('  name:', i['metadata']['name'])
        print('  addressType:', i.get('addressType'))
        print('  endpoints:', json.dumps(i.get('endpoints')))
        print('  ports:', json.dumps(i.get('ports')))
if not hit: print('  no etcd endpointslice')
"

echo ""
echo "############ E. how is the apiserver managed (for contrast)? ############"
kubectl -n kube-system get pods --no-headers 2>/dev/null | grep -E 'apiserver|scheduler|controller-manager|etcd' | sed 's/^/   /'

echo ""
echo "############ F. kubelet staticPodPath ############"
ssh -o BatchMode=yes -o ConnectTimeout=6 root@10.100.10.10 "grep -E 'staticPodPath' /var/lib/kubelet/config.yaml 2>&1" | sed 's/^/   /'

echo ""
echo "############ G. Prometheus: the etcd job has 0 discovered targets? ############"
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/targets?state=active' 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']['activeTargets']
jobs={}
for t in d:
    j=t['labels'].get('job','?')
    jobs[j]=jobs.get(j,0)+1
for k in sorted(jobs):
    if 'etcd' in k or 'kube' in k: print('   active job %-60s targets=%d' % (k, jobs[k]))
print('   does an etcd job appear among active targets?', any('etcd' in j for j in jobs))
"
echo "  --- scrape config for the etcd job (as Prometheus sees it) ---"
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/status/config' 2>/dev/null | python3 -c "
import sys,json,yaml
cfg=yaml.safe_load(json.load(sys.stdin)['data']['yaml'])
for sc in cfg['scrape_configs']:
    if 'etcd' in sc['job_name']:
        print('   job:', sc['job_name'])
        print('   kubernetes_sd_configs:', json.dumps(sc.get('kubernetes_sd_configs')))
        print('   relabelings:', json.dumps(sc.get('relabel_configs'),indent=2)[:900])
        print('   scheme:', sc.get('scheme'), 'path:', sc.get('metrics_path'), 'tls:', sc.get('tls_config'))
        print('   bearer:', sc.get('bearer_token_file'))
"
