#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=========== 1. 集群基础 ==========="
echo -n "节点: "; kubectl get nodes --no-headers | awk '{print $2}' | sort | uniq -c | tr '\n' ' '; echo
echo -n "非Running Pod: "; kubectl get pods -A --no-headers 2>/dev/null | grep -vc -E 'Running|Completed'
echo ""
echo "=========== 2. Gateway（对外暴露）==========="
kubectl get gateway -n gateway 2>/dev/null
echo "--- HTTPRoute"
kubectl get httproute -n gateway --no-headers 2>/dev/null | awk '{print "  "$1, $2, $3, $4}'
echo "--- 实测访问（带 Host 头）"
GWIP=$(kubectl get gateway monitoring-gateway -n gateway -o jsonpath='{.status.addresses[0].value}' 2>/dev/null)
echo "  Gateway IP: $GWIP"
for h in grafana prometheus alertmanager longhorn; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 -H "Host: $h.wuxing.local" "http://$GWIP/" 2>/dev/null)
  echo "  $h.wuxing.local -> HTTP $code"
done
echo ""
echo "=========== 3. 共享存储 ==========="
kubectl get sc 2>/dev/null
echo "--- Longhorn Pod 状态"
kubectl -n longhorn-system get pods --no-headers 2>/dev/null | awk '{print $2, $3}' | sort | uniq -c
echo "--- Longhorn 节点与磁盘"
kubectl -n longhorn-system get nodes.longhorn.io --no-headers 2>/dev/null | awk '{print "  "$1, $2, $3, $4, $5}' | head -12
echo ""
echo "=========== 4. 日志体系 ==========="
kubectl -n logging get pods --no-headers 2>/dev/null | awk '{print "  "$1, $2, $3}' || echo "  未部署"
echo "--- Loki 数据源连通性"
kubectl -n logging get svc --no-headers 2>/dev/null | awk '{print "  "$1, $2, $3, $5}'
echo ""
echo "=========== 5. metrics-server / kubectl top ==========="
kubectl -n kube-system get deploy metrics-server --no-headers 2>/dev/null || echo "  未部署"
kubectl top nodes 2>&1 | head -4
echo ""
echo "=========== 6. Prometheus remote_write ==========="
kubectl -n monitoring get prometheus prometheus-stack-kube-prom-prometheus -o jsonpath='{.spec.remoteWrite}' 2>/dev/null | head -c 300; echo
echo "--- monitoring Pod"
kubectl -n monitoring get pods --no-headers 2>/dev/null | awk '{print $2, $3}' | sort | uniq -c
