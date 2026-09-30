#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
cd /data1/ssdxt/charts/gateway-api
echo "=== 清理前"
ls -la
echo ""
echo "=== 删除 5 个 v1.2.1 旧文件"
rm -f gateway.networking.k8s.io_gatewayclasses.yaml \
      gateway.networking.k8s.io_gateways.yaml \
      gateway.networking.k8s.io_httproutes.yaml \
      gateway.networking.k8s.io_referencegrants.yaml \
      gateway.networking.k8s.io_tlsroutes.yaml
echo "  已删除"
echo ""
echo "=== 清理后"
ls -la
echo ""
echo "=== 验证集群 CRD 未受影响（应仍是 v1.6.1 的版本集合）"
for c in tlsroutes referencegrants httproutes grpcroutes backendtlspolicies; do
  echo -n "  $c: "
  kubectl get crd $c.gateway.networking.k8s.io -o jsonpath='{.spec.versions[*].name}' 2>&1
  echo "  (bundle: $(kubectl get crd $c.gateway.networking.k8s.io -o jsonpath='{.metadata.annotations.gateway\.networking\.k8s\.io/bundle-version}' 2>/dev/null))"
done
echo ""
echo "=== gatewayclass 状态（应仍为 True）"
kubectl get gatewayclass
echo ""
echo "=== 顺手检查别处有没有同样的小旧文件残留"
find /data1/ssdxt -name 'gateway.networking.k8s.io_*.yaml' 2>/dev/null | head -5 || true
echo "  (以上为空即无残留)"