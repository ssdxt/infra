#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== 1. Gateway 状态详情 ==="
kubectl get gateway monitoring-gateway -n gateway -o jsonpath='{.status.conditions}' 2>/dev/null | python3 -m json.tool 2>/dev/null | head -20
echo ""
echo "=== 2. Cilium 为 Gateway 创建的 Service ==="
kubectl get svc -A --no-headers 2>/dev/null | grep -iE 'cilium-gateway|NAME' | head -5
echo ""
echo "=== 3. kube-vip 的 svc_enable 值（决定能否给 LB 分 IP）==="
grep -A1 -E 'name: svc_enable|name: lb_enable|name: vip_interface|name: vip_cidr' /etc/kubernetes/manifests/kube-vip.yaml 2>/dev/null | grep -E 'name:|value:' | paste - - | sed 's/^/  /'
echo ""
echo "=== 4. 现有 LoadBalancer Service 是否拿到 IP ==="
kubectl get svc -A -o json 2>/dev/null | python3 -c '
import sys,json
d=json.load(sys.stdin)
n=0
for s in d["items"]:
    if s["spec"].get("type")=="LoadBalancer":
        ing=(s.get("status",{}).get("loadBalancer",{}).get("ingress") or [])
        print("  ", s["metadata"]["namespace"], s["metadata"]["name"], "->", [i.get("ip") for i in ing] or "PENDING")
        n+=1
if n==0: print("  无 LoadBalancer Service")
'
echo ""
echo "=== 5. 做一个最小 LoadBalancer 测试（看 kube-vip 到底能不能分 IP）==="
cat <<'YAML' | kubectl apply -f - >/dev/null 2>&1
apiVersion: v1
kind: Service
metadata:
  name: lb-test
  namespace: default
spec:
  type: LoadBalancer
  ports: [{port: 80, targetPort: 80}]
  selector: {app: none}
YAML
sleep 15
kubectl get svc lb-test -n default -o jsonpath='{.status.loadBalancer.ingress}' 2>/dev/null; echo
kubectl delete svc lb-test -n default >/dev/null 2>&1
echo ""
echo "=== 6. kube-vip pod 是否在跑 ==="
kubectl get pods -n kube-system --no-headers 2>/dev/null | grep kube-vip
