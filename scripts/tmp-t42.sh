#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf

crashcount() {  # $1=label selector  -> total restartCount + crashes in last N min
  kubectl -n "$2" get pods -l "$1" -o json 2>/dev/null | python3 -c "
import sys,json,datetime
d=json.load(sys.stdin)
now=datetime.datetime.now(datetime.timezone.utc)
tot=0; recent=0
for p in d['items']:
    for cs in (p['status'].get('containerStatuses') or []):
        tot+=cs.get('restartCount',0)
        t=(cs.get('lastState',{}).get('terminated') or {}).get('finishedAt')
        if t:
            dt=datetime.datetime.fromisoformat(t.replace('Z','+00:00'))
            if (now-dt).total_seconds()<600: recent+=1
print(f'{tot} {recent}')
"
}

echo "############ A. CORRECT restart accounting (jsonpath, not awk column) ############"
read CSI_T0 CSI_R0 <<< "$(crashcount 'app in (csi-provisioner,csi-attacher,csi-resizer,csi-snapshotter)' longhorn-system)"
read AL_T0 AL_R0 <<< "$(crashcount 'app.kubernetes.io/name=alloy' logging)"
echo "  baseline $(date +%H:%M:%S):  CSI restartCount=$CSI_T0 (crashes last10m=$CSI_R0)   ALLOY restartCount=$AL_T0 (crashes last10m=$AL_R0)"
echo "  --- per-pod restartCount ---"
kubectl -n longhorn-system get pods -l 'app in (csi-provisioner,csi-attacher,csi-resizer,csi-snapshotter)' -o jsonpath='{range .items[*]}{.metadata.name}{" restarts="}{.status.containerStatuses[0].restartCount}{"\n"}{end}' 2>&1
kubectl -n logging get pods -l app.kubernetes.io/name=alloy -o jsonpath='{range .items[*]}{.metadata.name}{" restarts="}{.status.containerStatuses[0].restartCount}{"\n"}{end}' 2>&1 | head -3

echo ""
echo "############ B. CURRENT log correctness (lines written in last 2 min only) ############"
S=$(( $(date +%s) - 120 ))
kubectl -n logging exec loki-0 -c loki -- wget -qO- "http://localhost:3100/loki/api/v1/query_range?query=%7Bjob%3D%22pods%22%7D&start=${S}000000000&limit=200" 2>&1 | python3 -c "
import sys,json,re
d=json.load(sys.stdin); res=d['data']['result']
rx=re.compile(r'/var/log/pods/([^_]+)_([^_]+)_([^/]+)/([^/]+)/')
withns=without=cri=clean=ok=bad=0
for s in res:
    st=s['stream']; fn=st.get('filename','')
    if st.get('namespace'): withns+=1
    else: without+=1
    m=rx.match(fn)
    if m and st.get('namespace'):
        if (m.group(1),m.group(2),m.group(4))==(st.get('namespace'),st.get('pod'),st.get('container')): ok+=1
        else: bad+=1
    for v in s['values']:
        if ' stdout F ' in v[1] or ' stderr F ' in v[1]: cri+=1
        else: clean+=1
print(f'  streams with namespace label: {withns}   without: {without}')
print(f'  label triple consistent: {ok}   inconsistent: {bad}')
print(f'  lines clean: {clean}   still carrying CRI prefix: {cri}')
" 2>&1

echo ""
echo "############ C. apiserver pods/log load ############"
G=$(kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/query?query=sum(apiserver_longrunning_requests%7Bresource%3D%22pods%22%2Csubresource%3D%22log%22%7D)' 2>/dev/null | python3 -c "import sys,json;r=json.load(sys.stdin)['data']['result'];print(r[0]['value'][1] if r else 0)")
R=$(kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/query?query=sum(rate(apiserver_request_total%7Bresource%3D%22pods%22%2Csubresource%3D%22log%22%2Cverb%3D%22CONNECT%22%7D%5B5m%5D))' 2>/dev/null | python3 -c "import sys,json;r=json.load(sys.stdin)['data']['result'];print(round(float(r[0]['value'][1]),3) if r else 0)")
echo "  pods/log long-running gauge = $G    new CONNECT/s = $R"

echo ""
echo "############ D. 6-minute quiet observation ############"
for i in 1 2 3 4 5 6; do
  sleep 60
  read C_T C_R <<< "$(crashcount 'app in (csi-provisioner,csi-attacher,csi-resizer,csi-snapshotter)' longhorn-system)"
  read A_T A_R <<< "$(crashcount 'app.kubernetes.io/name=alloy' logging)"
  echo "  t=${i}min  CSI restartCount=$C_T (delta +$((C_T-CSI_T0)), crashes last10m=$C_R)   ALLOY restartCount=$A_T (delta +$((A_T-AL_T0)), crashes last10m=$A_R)"
done

echo ""
echo "############ E. final states ############"
kubectl -n logging get ds alloy
kubectl -n logging get pods --no-headers | awk '{print $2,$3}' | sort | uniq -c
kubectl -n longhorn-system get pods --no-headers | awk '{print $2,$3}' | sort | uniq -c
kubectl -n longhorn-system get pods --no-headers | grep -vE 'Running|Completed' || echo "  longhorn: none bad"
echo "  end $(date +%H:%M:%S)"
