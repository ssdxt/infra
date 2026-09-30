#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== [1] kubelet :10250 established connections per node (real active log/exec streams) ==="
for ip in 10.100.10.10 10.100.10.14 10.100.10.19 10.100.10.33 10.100.10.34 10.100.10.39 10.100.10.41 10.100.10.44 10.100.10.45 10.100.10.46 10.100.10.47; do
  n=$(ssh -o BatchMode=yes -o ConnectTimeout=6 root@$ip "ss -tnH state established '( sport = :10250 )' 2>/dev/null | wc -l" 2>/dev/null)
  printf "  %-14s established->10250: %s\n" "$ip" "${n:-?}"
done

echo ""
echo "=== [2] total pods/log CONNECT rate right now (1m avg) ==="
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/query?query=sum(rate(apiserver_request_total%7Bresource%3D%22pods%22%2Csubresource%3D%22log%22%2Cverb%3D%22CONNECT%22%7D%5B1m%5D))' 2>&1 | head -c 250

echo ""
echo "=== [3] is apiserver audit logging enabled? ==="
kubectl -n kube-system get pods -l component=kube-apiserver -o jsonpath='{.items[0].spec.containers[0].command}' 2>/dev/null | tr ',' '\n' | grep -i audit || echo "  no audit flags"

echo ""
echo "=== [4] other pods referencing pod-log streaming? ==="
kubectl get pods -A -o json 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)
hits=0
for p in d['items']:
    spec=p['spec']
    for c in (spec.get('containers') or [])+(spec.get('initContainers') or []):
        blob=json.dumps(c)
        if 'source.kubernetes' in blob or '--follow' in blob or 'pods/log' in blob:
            print('  ', p['metadata']['namespace'], p['metadata']['name'], c['name']); hits+=1
print('  hits:', hits, ' total pods:', len(d['items']))
"

echo ""
echo "=== [5] long-running CONNECT breakdown on this apiserver ==="
kubectl get --raw='/metrics' 2>/dev/null | grep '^apiserver_longrunning_requests{' | grep -E 'subresource="(log|exec|attach|portforward)"' | head -10

echo ""
echo "=== [6] request terminations (are old streams being closed?) ==="
kubectl get --raw='/metrics' 2>/dev/null | grep -E '^apiserver_request_terminations_total' | head -5
