#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=monitoring; PROM=prometheus-stack-kube-prom-prometheus

echo "===== [0] 应用前 out-of-order 基线(plant01 侧另测) ====="
echo "  当前 spec.remoteWrite:"
kubectl -n $NS get prometheus $PROM -o jsonpath='{.spec.remoteWrite[0].writeRelabelConfigs}' | python3 -m json.tool

echo
echo "===== [1] server-side dry-run 校验 ====="
if kubectl -n $NS patch prometheus $PROM --type merge --patch-file /tmp/remote-write-patch3.yaml --dry-run=server >/dev/null 2>&1; then
  echo "  ✅ dry-run 通过"
else
  echo "  ❌ dry-run 失败"; kubectl -n $NS patch prometheus $PROM --type merge --patch-file /tmp/remote-write-patch3.yaml --dry-run=server 2>&1 | head -5; exit 1
fi

echo
echo "===== [2] 正式应用 ====="
kubectl -n $NS patch prometheus $PROM --type merge --patch-file /tmp/remote-write-patch3.yaml

echo
echo "===== [3] 等待热加载(60s) ====="
sleep 60
kubectl -n $NS logs prometheus-$PROM-0 -c config-reloader --tail 3 2>&1 | grep -i reload
kubectl -n $NS exec prometheus-$PROM-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/status/runtimeinfo' 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']
print('  reloadConfigSuccess =',d.get('reloadConfigSuccess'),' lastConfigTime =',d.get('lastConfigTime'))"

echo
echo "===== [4] 渲染结果确认 ====="
kubectl -n $NS exec prometheus-$PROM-0 -c prometheus -- sh -c \
  'awk "/^remote_write:/,/^[a-z_]+\$/" /etc/prometheus/config_out/prometheus.env.yaml' 2>&1

echo
echo "===== [5] 队列健康(60s 后) ====="
sleep 30
for m in prometheus_remote_storage_samples_pending prometheus_remote_storage_samples_total prometheus_remote_storage_shards; do
  printf '  %-50s ' "$m"
  kubectl -n $NS exec prometheus-$PROM-0 -c prometheus -- wget -qO- "http://localhost:9090/api/v1/query?query=$m" 2>/dev/null | python3 -c "
import sys,json
try:
  r=json.load(sys.stdin)['data']['result']; print(r[0]['value'][1] if r else '0')
except Exception as e: print('ERR')"
done
printf '  %-50s ' "failed_samples_total"
kubectl -n $NS exec prometheus-$PROM-0 -c prometheus -- wget -qO- "http://localhost:9090/api/v1/query?query=prometheus_remote_storage_failed_samples_total" 2>/dev/null | python3 -c "
import sys,json
try:
  r=json.load(sys.stdin)['data']['result']; print(r[0]['value'][1] if r else '0 (无失败)')
except: print('0 (无失败)')"
