#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== 1. Cilium helm 是谁升的、镜像修复还在吗 ====="
helm -n kube-system history cilium 2>/dev/null | tail -3 | sed 's/^/  /'
echo -n "  hubble-relay 启用值: "
helm -n kube-system get values cilium 2>/dev/null | grep -A2 "relay" | head -4 | sed 's/^/  /'
echo "  --- 4 个镜像修复核对："
kubectl -n kube-system get ds cilium -o jsonpath='agent容器名: {.spec.template.spec.containers[0].name}{"\n"}  agent镜像: {.spec.template.spec.containers[0].image}{"\n"}' 2>/dev/null | sed 's/^/  /'
kubectl -n kube-system get deploy cilium-operator -o jsonpath='operator镜像: {.spec.template.spec.containers[0].image}{"\n"}  operator命令: {.spec.template.spec.containers[0].command}{"\n"}' 2>/dev/null | sed 's/^/  /'
echo -n "  cilium Pod 状态: "
kubectl -n kube-system get pods -l k8s-app=cilium --no-headers 2>/dev/null | awk '{print $3}' | sort | uniq -c | tr '\n' ' '; echo ""
echo -n "  cilium-operator 状态: "
kubectl -n kube-system get pods -l io.cilium/app=operator --no-headers 2>/dev/null | awk '{print $2, $3, "重启="$4}' | tr '\n' ' '; echo ""
echo ""

echo "===== 2. 修复 hubble-relay OOM（加资源）====="
CN=$(kubectl -n kube-system get deploy hubble-relay -o jsonpath='{.spec.template.spec.containers[0].name}' 2>/dev/null)
kubectl -n kube-system set resources deploy/hubble-relay --containers=$CN \
  --limits=memory=512Mi,cpu=500m --requests=memory=128Mi,cpu=100m 2>&1 | tail -1
kubectl -n kube-system rollout status deploy/hubble-relay --timeout=180s 2>&1 | tail -1
kubectl -n kube-system get pods | grep hubble-relay | sed 's/^/  /'
echo ""

echo "===== 3. adapter CPU 提到 2 核（彻底解决限流）====="
python3 - <<'PY'
try:
    import yaml
    p = "/data1/ssdxt/values/prometheus-adapter-values.yaml"
    d = yaml.safe_load(open(p))
    d.setdefault("resources", {}).setdefault("limits", {})["cpu"] = "2"
    open(p, "w").write(yaml.safe_dump(d, sort_keys=False, allow_unicode=True))
    print("  ✅ values: limits.cpu=2")
except Exception as e:
    print("  ⚠️ values 未改:", e)
PY
CN2=$(kubectl -n monitoring get deploy prometheus-adapter -o jsonpath='{.spec.template.spec.containers[0].name}')
kubectl -n monitoring set resources deploy/prometheus-adapter --containers=$CN2 --limits=cpu=2 2>&1 | tail -1
kubectl -n monitoring rollout status deploy/prometheus-adapter --timeout=180s 2>&1 | tail -1
kubectl -n monitoring get pods | grep adapter | sed 's/^/  /'
echo ""

echo "===== 4. 最终健康快照 ====="
echo -n "  全集群非 Running Pod: "
kubectl get pods -A --no-headers 2>/dev/null | grep -vE "Running|Completed" | wc -l
echo -n "  hubble-relay: "; kubectl -n kube-system get pods | grep hubble-relay | awk '{print $3}' 
echo -n "  etcd 三成员: "
OK=0; for ip in 10.100.10.10 10.100.10.14 10.100.10.19; do
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$ip \
   'etcdctl --cacert=/etc/kubernetes/pki/etcd/ca.crt --cert=/etc/kubernetes/pki/etcd/client.crt --key=/etc/kubernetes/pki/etcd/client.key --endpoints=https://'$ip':2379 endpoint health 2>/dev/null | grep -q healthy && echo -n "✓"' 2>/dev/null
done; echo ""
echo -n "  VIP .250/.251: "
kubectl -n gateway get svc cilium-gateway-monitoring-gateway -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null; echo ""