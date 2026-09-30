#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== doc written? ==="
ls -la /data1/ssdxt/storage/longhorn-webhook-tls-issue.md
head -8 /data1/ssdxt/storage/longhorn-webhook-tls-issue.md
echo ""
echo "=== confirm my dry-run probe created NOTHING ==="
kubectl -n longhorn-system get volumes.longhorn.io webhook-probe 2>&1 | tail -1
kubectl -n longhorn-system get volumes.longhorn.io --no-headers 2>&1 | wc -l | sed 's/^/  volumes in longhorn-system: /'
echo ""
echo "=== confirm secrets untouched (no static annotation, RV still moving) ==="
kubectl -n longhorn-system get secret longhorn-webhook-tls longhorn-webhook-ca -o jsonpath='{range .items[*]}{.metadata.name} annotations={.metadata.annotations}{"\n"}{end}' 2>&1 | grep -o 'listener.cattle.io/static' | wc -l | sed 's/^/  static annotations present: /'
echo "  rv1=$(kubectl -n longhorn-system get secret longhorn-webhook-tls -o jsonpath='{.metadata.resourceVersion}')"
sleep 15
echo "  rv2=$(kubectl -n longhorn-system get secret longhorn-webhook-tls -o jsonpath='{.metadata.resourceVersion}')  (仍在增长 = 我确实没动它)"
echo ""
echo "=== longhorn/其他组件状态未变 ==="
kubectl -n longhorn-system get pods --no-headers | awk '{print $2,$3}' | sort | uniq -c
helm -n longhorn-system list 2>&1 | tail -2