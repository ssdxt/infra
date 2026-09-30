#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf

echo "############ A. why did csi-provisioner exit 255? (previous logs) ############"
P=csi-provisioner-7bdc75dddd-bjzcx
kubectl -n longhorn-system logs $P --previous --tail=15 2>&1 | tail -15
echo ""
echo "--- csi-attacher previous ---"
P2=$(kubectl -n longhorn-system get pods -l app=csi-attacher --no-headers | awk '{print $1}' | head -1)
kubectl -n longhorn-system logs $P2 --previous --tail=8 2>&1 | tail -8

echo ""
echo "############ B. CSI deployment leader-election args ############"
kubectl -n longhorn-system get deploy csi-provisioner -o jsonpath='{.spec.template.spec.containers[0].args}' 2>&1
echo ""
kubectl -n longhorn-system get deploy csi-provisioner -o jsonpath='{.spec.template.spec.containers[0].command}' 2>&1

echo ""
echo "############ C. apiserver latency (max over last 5m) ############"
kubectl get --raw='/metrics' 2>/dev/null | grep -E '^apiserver_request_duration_seconds_(sum|count)\{' | head -2
echo "--- current API responsiveness (time a few calls) ---"
for i in 1 2 3; do
  /usr/bin/time -f "  kubectl get pods -A: %es" kubectl get pods -A --no-headers 2>&1 >/dev/null | tail -1
done

echo ""
echo "############ D. alloy mounts / log source mode ############"
kubectl -n logging get ds alloy -o jsonpath='{range .spec.template.spec.containers[0].volumeMounts[*]}{.name} -> {.mountPath}{"\n"}{end}' 2>&1
echo "--- volumes ---"
kubectl -n logging get ds alloy -o jsonpath='{range .spec.template.spec.volumes[*]}{.name}{"\n"}{end}' 2>&1

echo ""
echo "############ E. restart trend for CSI pods (count per hour bucket) ############"
kubectl -n longhorn-system get pods -o json | python3 -c "
import sys,json,datetime,collections
d=json.load(sys.stdin)
now=datetime.datetime.now(datetime.timezone.utc)
buckets=collections.Counter()
for p in d['items']:
    for cs in (p['status'].get('containerStatuses') or []):
        # count restarts per pod is cumulative; use lastState finishedAt
        lc=cs.get('lastState',{}).get('terminated')
        if lc and lc.get('finishedAt'):
            dt=datetime.datetime.fromisoformat(lc['finishedAt'].replace('Z','+00:00'))
            m=int((now-dt).total_seconds()//300)*5
            buckets[m]+=1
for m in sorted(buckets):
    print(f'   ~{m:3d} min ago: {buckets[m]} crash(es)')
print('   sum of restartCount:', sum((cs.get('restartCount',0)) for p in d['items'] for cs in (p['status'].get('containerStatuses') or [])))
"

echo ""
echo "############ F. is the API being hammered by pods/log streams? ############"
kubectl get --raw='/metrics' 2>/dev/null | grep -E 'apiserver_current_inflight_requests|apiserver_longrunning_requests' | head -6
