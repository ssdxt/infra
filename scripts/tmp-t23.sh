#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf

echo "############ A. Grafana -> Loki health (correct uid) ############"
PW=$(kubectl -n monitoring get secret prometheus-stack-grafana -o jsonpath='{.data.admin-password}' | base64 -d)
DSJSON=$(kubectl -n monitoring exec deploy/prometheus-stack-grafana -c grafana -- sh -c "wget -qO- 'http://admin:$PW@localhost:3000/api/datasources'" 2>/dev/null)
LUID_LOKI=$(echo "$DSJSON" | python3 -c "import sys,json; print([d['uid'] for d in json.load(sys.stdin) if d['type']=='loki'][0])" 2>&1)
echo "  loki datasource uid = $LUID_LOKI"
echo "  --- /health ---"
kubectl -n monitoring exec deploy/prometheus-stack-grafana -c grafana -- sh -c "wget -qO- 'http://admin:$PW@localhost:3000/api/datasources/uid/$LUID_LOKI/health'" 2>&1 | head -c 400
echo ""
echo "  --- proxy /loki/api/v1/labels through Grafana ---"
kubectl -n monitoring exec deploy/prometheus-stack-grafana -c grafana -- sh -c "wget -qO- 'http://admin:$PW@localhost:3000/api/datasources/proxy/uid/$LUID_LOKI/loki/api/v1/labels'" 2>&1 | head -c 400
echo ""
echo "  --- proxy LogQL query through Grafana ---"
kubectl -n monitoring exec deploy/prometheus-stack-grafana -c grafana -- sh -c "wget -qO- 'http://admin:$PW@localhost:3000/api/datasources/proxy/uid/$LUID_LOKI/loki/api/v1/query?query=sum(count_over_time(%7Bnamespace%3D%22kube-system%22%7D%5B5m%5D))'" 2>&1 | head -c 400

echo ""
echo "############ B. csi-provisioner error analysis ############"
kubectl -n longhorn-system get pods -l app=csi-provisioner -o wide
echo "--- not-running csi pods ---"
for p in $(kubectl -n longhorn-system get pods -l app=csi-provisioner --no-headers | awk '$3!="Running"{print $1}'); do
  echo "  == $p =="
  kubectl -n longhorn-system logs $p --tail=6 2>&1 | tail -6
done
echo "--- restart timestamps across all longhorn pods (last 10m) ---"
kubectl -n longhorn-system get pods -o json | python3 -c "
import sys,json,datetime
d=json.load(sys.stdin)
now=datetime.datetime.now(datetime.timezone.utc)
rows=[]
for p in d['items']:
    for cs in (p['status'].get('containerStatuses') or []):
        lc=cs.get('lastState',{}).get('terminated')
        if lc:
            t=lc.get('finishedAt')
            if t:
                dt=datetime.datetime.fromisoformat(t.replace('Z','+00:00'))
                rows.append(((now-dt).total_seconds(), p['metadata']['name'], cs['name'], lc.get('exitCode'), lc.get('reason')))
rows.sort()
for secs,name,c,code,reason in rows[:12]:
    print(f'   {secs/60:6.1f} min ago  {name:52s} {c:14s} exit={code} {reason}')
print('   total terminated-container events:', len(rows))
"

echo ""
echo "############ C. API server latency sanity ############"
timeout 25 kubectl get --raw='/readyz?verbose' 2>&1 | tail -4
echo "--- etcd/apiserver pod restarts ---"
kubectl -n kube-system get pods -l component=kube-apiserver --no-headers 2>/dev/null | head -5
kubectl -n kube-system get pods --no-headers 2>/dev/null | grep -E 'etcd|apiserver' | head -5
