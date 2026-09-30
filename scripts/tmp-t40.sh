#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
P=http://localhost:3100

echo "############ A. LABEL CORRECTNESS (filename path must match namespace/pod/container) ############"
kubectl -n logging exec loki-0 -c loki -- wget -qO- "http://localhost:3100/loki/api/v1/query_range?query=%7Bjob%3D%22pods%22%7D&limit=60" 2>&1 | python3 -c "
import sys,json,re
d=json.load(sys.stdin)
res=d['data']['result']
if not res: print('  NO RESULTS'); sys.exit()
rx=re.compile(r'/var/log/pods/([^_]+)_([^_]+)_([^/]+)/([^/]+)/')
ok=bad=0; examples=[]; cri=0; clean=0
for s in res:
    fn=s['stream'].get('filename','')
    m=rx.match(fn)
    if not m: continue
    exp=(m.group(1),m.group(2),m.group(4))
    got=(s['stream'].get('namespace'),s['stream'].get('pod'),s['stream'].get('container'))
    if exp==got:
        ok+=1; examples.append((s['stream'],s['values'][0][1] if s['values'] else ''))
    else:
        bad+=1
        if bad<=3: print('  MISMATCH exp=',exp,'got=',got)
    for v in s['values']:
        if ' stdout F ' in v[1] or ' stderr F ' in v[1]: cri+=1
        else: clean+=1
print(f'  streams label-consistent: {ok}   inconsistent: {bad}')
print(f'  log lines with CRI prefix still present: {cri}   clean: {clean}')
print()
for st,line in examples[:3]:
    print('  SAMPLE labels:', json.dumps({k:st[k] for k in (\"namespace\",\"pod\",\"container\",\"node\",\"stream\") if k in st},ensure_ascii=False))
    print('         line   :', repr(line[:120]))
" 2>&1

echo ""
echo "############ B. LogQL volume by namespace (5m) ############"
kubectl -n logging exec loki-0 -c loki -- wget -qO- "http://localhost:3100/loki/api/v1/query?query=sum(count_over_time(%7Bjob%3D%22pods%22%7D%5B5m%5D))by(namespace)" 2>&1 | python3 -c "
import sys,json
d=json.load(sys.stdin)
for r in sorted(d['data']['result'],key=lambda x:-float(x['value'][1])):
    print('   ',r['metric'].get('namespace'),'->',r['value'][1])
" 2>&1

echo ""
echo "############ C. BASELINE for stability watch ############"
B_CSI=$(kubectl -n longhorn-system get pods -l 'app in (csi-provisioner,csi-attacher,csi-resizer,csi-snapshotter)' --no-headers | awk '{s+=$5} END {print s}')
B_ALL=$(kubectl -n logging get pods -l app.kubernetes.io/name=alloy --no-headers | awk '{s+=$5} END {print s}')
G0=$(kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/query?query=sum(apiserver_longrunning_requests%7Bresource%3D%22pods%22%2Csubresource%3D%22log%22%7D)' 2>/dev/null | python3 -c "import sys,json;r=json.load(sys.stdin)['data']['result'];print(r[0]['value'][1] if r else 0)")
echo "  baseline: csi_restarts=$B_CSI  alloy_restarts=$B_ALL  pods/log_gauge=$G0  at $(date +%H:%M:%S)"

echo ""
echo "############ D. quiet observation: 8 samples / 60s ############"
for i in $(seq 1 8); do
  sleep 60
  CSI=$(kubectl -n longhorn-system get pods -l 'app in (csi-provisioner,csi-attacher,csi-resizer,csi-snapshotter)' --no-headers | awk '{s+=$5} END {print s}')
  AL=$(kubectl -n logging get pods -l app.kubernetes.io/name=alloy --no-headers | awk '{s+=$5} END {print s}')
  GG=$(kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/query?query=sum(apiserver_longrunning_requests%7Bresource%3D%22pods%22%2Csubresource%3D%22log%22%7D)' 2>/dev/null | python3 -c "import sys,json;r=json.load(sys.stdin)['data']['result'];print(r[0]['value'][1] if r else 0)")
  RT=$(kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/query?query=sum(rate(apiserver_request_total%7Bresource%3D%22pods%22%2Csubresource%3D%22log%22%2Cverb%3D%22CONNECT%22%7D%5B2m%5D))' 2>/dev/null | python3 -c "import sys,json;r=json.load(sys.stdin)['data']['result'];print(round(float(r[0]['value'][1]),2) if r else 0)")
  echo "  t=$((i))min  csi_restarts=$CSI (+$((CSI-B_CSI)))  alloy_restarts=$AL (+$((AL-B_ALL)))  pods/log_gauge=$GG  new-CONNECT/s=$RT"
done
echo "  end at $(date +%H:%M:%S)"
echo ""
echo "=== final pod states ==="
kubectl -n logging get ds alloy
kubectl -n logging get pods --no-headers | awk '{print $2,$3}' | sort | uniq -c
kubectl -n longhorn-system get pods --no-headers | awk '{print $2,$3}' | sort | uniq -c
kubectl -n longhorn-system get pods --no-headers | grep -vE 'Running|Completed' || echo "  longhorn: none bad"
