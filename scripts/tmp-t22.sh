#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf

echo "############ 1. LONGHORN ############"
echo "--- pods (status counts) ---"
kubectl -n longhorn-system get pods --no-headers | awk '{print $2, $3}' | sort | uniq -c
echo "--- not Running/Succeeded ---"
kubectl -n longhorn-system get pods --no-headers | grep -vE 'Running|Completed' || echo "  (none)"
echo "--- storageclass ---"
kubectl get sc
echo "--- longhorn-frontend svc ---"
kubectl -n longhorn-system get svc longhorn-frontend
echo "--- settings ---"
kubectl -n longhorn-system get settings.longhorn.io default-replica-count default-data-path -o jsonpath='{range .items[*]}{.metadata.name}={.value}{"\n"}{end}'
echo "--- longhorn nodes ---"
kubectl -n longhorn-system get nodes.longhorn.io --no-headers | wc -l
echo "--- live PVCs on longhorn ---"
kubectl get pvc -A -o custom-columns=NS:.metadata.namespace,NAME:.metadata.name,SC:.spec.storageClassName,STATUS:.status.phase,VOL:.spec.volumeName

echo ""
echo "############ 2. LOGGING ############"
echo "--- daemonset/pods ---"
kubectl -n logging get ds
kubectl -n logging get pods --no-headers | awk '{print $2, $3}' | sort | uniq -c
echo "--- svc ---"
kubectl -n logging get svc
echo "--- pvc ---"
kubectl -n logging get pvc
echo "--- Loki labels ---"
kubectl -n logging exec loki-0 -c loki -- wget -qO- 'http://localhost:3100/loki/api/v1/labels' 2>&1 | head -c 400
echo ""
echo "--- LogQL: top namespaces by volume (5m) ---"
kubectl -n logging exec loki-0 -c loki -- wget -qO- 'http://localhost:3100/loki/api/v1/query?query=sum(count_over_time(%7Bnamespace%3D~%22.%2B%22%7D%5B5m%5D))by(namespace)' 2>&1 | python3 -c "import sys,json; d=json.load(sys.stdin); [print('   ',r['metric'].get('namespace'),'->',r['value'][1],'lines') for r in d['data']['result']]" 2>&1
echo "--- LogQL: actual log line sample ---"
kubectl -n logging exec loki-0 -c loki -- wget -qO- 'http://localhost:3100/loki/api/v1/query_range?query=%7Bnamespace%3D%22monitoring%22%7D&limit=1' 2>&1 | python3 -c "
import sys,json
d=json.load(sys.stdin)
for s in d['data']['result'][:1]:
    print('    labels:', json.dumps(s['stream'],ensure_ascii=False))
    for v in s['values'][:1]:
        print('    time  :', v[0])
        print('    line  :', v[1][:160])
" 2>&1
echo "--- alloy pulling logs ok (errors?) ---"
kubectl -n logging logs -l app.kubernetes.io/name=alloy --tail=200 2>/dev/null | grep -iE 'level=error|panic|failed' | tail -5 || echo "  (no errors)"
echo "--- alloy DaemonSet available ---"
kubectl -n logging get ds alloy -o jsonpath='ready={.status.numberReady}/{.status.desiredNumberScheduled} available={.status.numberAvailable}{"\n"}'

echo ""
echo "############ 3. METRICS-SERVER ############"
kubectl -n kube-system get pods -l k8s-app=metrics-server
kubectl get apiservice v1beta1.metrics.k8s.io --no-headers
echo "--- kubectl top nodes ---"
kubectl top nodes
echo "--- kubectl top pods -A (head 5) ---"
kubectl top pods -A | head -5

echo ""
echo "############ 4. GRAFANA DATASOURCE ############"
kubectl -n monitoring get cm loki-datasource --show-labels
PW=$(kubectl -n monitoring get secret prometheus-stack-grafana -o jsonpath='{.data.admin-password}' | base64 -d)
UID=$(kubectl -n monitoring get cm loki-datasource -o jsonpath='{.data.loki-ds\.yaml}' >/dev/null 2>&1; echo "P8E80F9AEF21F6940")
echo "--- Grafana datasource health ---"
kubectl -n monitoring exec deploy/prometheus-stack-grafana -c grafana -- sh -c "wget -qO- 'http://admin:$PW@localhost:3000/api/datasources/uid/$UID/health'" 2>&1 | head -c 400
echo ""
echo "--- Grafana datasource names ---"
kubectl -n monitoring exec deploy/prometheus-stack-grafana -c grafana -- sh -c "wget -qO- 'http://admin:$PW@localhost:3000/api/datasources'" 2>&1 | python3 -c "import sys,json; [print('   ',d['name'],'|',d['type'],'|',d['url'],'| default=',d['isDefault']) for d in json.load(sys.stdin)]" 2>&1
echo "--- grafana sidecar recent errors? ---"
kubectl -n monitoring logs deploy/prometheus-stack-grafana -c grafana-sc-datasources --tail=5 2>&1 | tail -5

echo ""
echo "############ 5. leftovers ############"
kubectl get ns stotest 2>&1 | tail -1
