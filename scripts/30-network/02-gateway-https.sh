#!/bin/bash
# 02-gateway-https.sh —— Gateway HTTPS 化幂等脚本（cert-manager 自建 CA + *.wuxing.local 泛域名证书）
# 依赖：cert-manager 1.16.1、Cilium Gateway API（见 30-网络与CNI/gateway-https.md）
# 可重复执行；改动前自动备份到 /data1/ssdxt/gateway/backup/<ts>/
set -e
export KUBECONFIG=/etc/kubernetes/admin.conf
DIR=/data1/ssdxt/gateway
TS=$(date +%Y%m%d-%H%M%S)
BK=$DIR/backup/$TS
mkdir -p $BK

echo "== 0. 备份 =="
kubectl -n gateway get gateway monitoring-gateway -o yaml > $BK/gateway.yaml
kubectl -n gateway get httproute -o yaml > $BK/httproutes.yaml
kubectl -n argocd get cm argocd-cmd-params-cm -o yaml > $BK/argocd-cm.yaml
kubectl -n argocd get svc argocd-server -o yaml > $BK/argocd-svc.yaml
kubectl -n longhorn-system get svc longhorn-frontend -o yaml > $BK/longhorn-svc.yaml
kubectl -n gateway get svc cilium-gateway-monitoring-gateway -o yaml > $BK/gateway-svc.yaml

echo "== 1. CA + 泛域名证书 =="
kubectl apply -f $DIR/wxq-ca.yaml
for i in $(seq 1 30); do
  R=$(kubectl -n gateway get certificate wxq-wildcard-tls -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
  [ "$R" = "True" ] && break; sleep 2
done
[ "$R" = "True" ] || { echo "证书未 Ready"; exit 1; }
kubectl -n cert-manager get secret wxq-root-ca -o jsonpath='{.data.ca\.crt}' | base64 -d > $DIR/wxq-root-ca.crt

echo "== 2. Gateway 加 HTTPS 443 监听 =="
kubectl -n gateway patch gateway monitoring-gateway --type merge -p '{"spec":{"listeners":[{"name":"http","protocol":"HTTP","port":80,"allowedRoutes":{"namespaces":{"from":"All"}}},{"name":"https","protocol":"HTTPS","port":443,"tls":{"certificateRefs":[{"group":"","kind":"Secret","name":"wxq-wildcard-tls"}]},"allowedRoutes":{"namespaces":{"from":"All"}}}]}}'
sleep 5
kubectl -n gateway get gateway monitoring-gateway -o jsonpath='{.status.conditions}'; echo

echo "== 3. 固定 nodePort：32298=HTTPS(443)、32299=HTTP(80) =="
# 注意：Cilium 会重建 gateway svc，必须用它的端口名 port-80/port-443 patch，否则被改回随机端口
kubectl -n gateway patch svc cilium-gateway-monitoring-gateway --type merge -p '{"spec":{"ports":[{"name":"port-80","port":80,"protocol":"TCP","nodePort":32299},{"name":"port-443","port":443,"protocol":"TCP","nodePort":32298}]}}'
sleep 5
kubectl -n gateway get svc cilium-gateway-monitoring-gateway -o jsonpath='{.spec.ports}'; echo

echo "== 4. ArgoCD insecure + HTTPRoute =="
kubectl -n argocd patch cm argocd-cmd-params-cm --type merge -p '{"data":{"server.insecure":"true"}}'
kubectl -n argocd rollout restart deploy/argocd-server
kubectl -n argocd rollout status deploy/argocd-server --timeout=180s
kubectl apply -f $DIR/argocd-httproute.yaml
kubectl apply -f $DIR/argocd-referencegrant.yaml

echo "== 5. HTTP->HTTPS 跳转（每条 route 头部插入独立 redirect rule，跳到 32298） =="
# RequestRedirect 不能与 backendRefs 同 rule；redirect 端口显式写 32298
# （工位没有 .251/.10:443 路由，443 只以 nodePort 32298 暴露；默认跳 443 工位会断）
for r in grafana-route prometheus-route alertmanager-route longhorn-route monitoring-routes; do
  FIRST=$(kubectl -n gateway get httproute $r -o jsonpath='{.spec.rules[0].filters[0].type}' 2>/dev/null)
  if [ "$FIRST" = "RequestRedirect" ]; then
    kubectl -n gateway patch httproute $r --type json \
      -p '[{"op":"replace","path":"/spec/rules/0/filters/0/requestRedirect","value":{"scheme":"https","port":32298,"statusCode":301}}]'
  else
    kubectl -n gateway patch httproute $r --type json \
      -p '[{"op":"add","path":"/spec/rules/0","value":{"filters":[{"type":"RequestRedirect","requestRedirect":{"scheme":"https","port":32298,"statusCode":301}}]}}]'
  fi
done

echo "== 6. NodePort 清理 =="
kubectl -n longhorn-system patch svc longhorn-frontend -p '{"spec":{"type":"ClusterIP"}}' || true
kubectl -n argocd patch svc argocd-server -p '{"spec":{"type":"ClusterIP"}}' || true

echo "== 7. 验证 =="
for h in grafana longhorn alertmanager prometheus argocd; do
  curl -sk --resolve $h.wuxing.local:32298:10.100.10.10 https://$h.wuxing.local:32298/ -o /dev/null -w "%{http_code} "
done; echo
curl -s --cacert $DIR/wxq-root-ca.crt --resolve grafana.wuxing.local:32298:10.100.10.10 https://grafana.wuxing.local:32298/ -o /dev/null -w "cert-chain: %{http_code}\n"
curl -skL --resolve grafana.wuxing.local:32298:10.100.10.10 -o /dev/null -w "redirect-chain: %{http_code} final=%{url_effective}\n" -H 'Host: grafana.wuxing.local' http://10.100.10.10:32299/
echo "DONE (备份: $BK)"
