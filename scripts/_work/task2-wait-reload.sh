#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=monitoring; PROM=prometheus-stack-kube-prom-prometheus; CP=prometheus-$PROM-0

echo "===== [1] CRD spec 是否已含第 4 条 drop 规则 ====="
kubectl -n $NS get prometheus $PROM -o jsonpath='{.spec.remoteWrite[0].writeRelabelConfigs}' | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('  规则条数 =',len(d))
for i,r in enumerate(d,1):
    print('   %d) action=%-6s regex=%s' % (i,r['action'],r['regex'][:90]))
"
echo
echo "===== [2] 等待 config-reloader 触发(最多 180s) ====="
for i in $(seq 1 18); do
  LCT=$(kubectl -n $NS exec $CP -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/status/runtimeinfo' 2>/dev/null | python3 -c "
import sys,json
try: print(json.load(sys.stdin)['data'].get('lastConfigTime'))
except: print('NA')")
  N=$(kubectl -n $NS exec $CP -c prometheus -- sh -c 'grep -c "action: drop" /etc/prometheus/config_out/prometheus.env.yaml' 2>/dev/null)
  echo "  [$((i*10))s] lastConfigTime=$LCT  drop规则数=$N"
  if [ "$N" = "3" ]; then echo "  ✅ 已渲染 3 条 drop(共 4 条规则), 配置已更新"; break; fi
  sleep 10
done
echo
echo "===== [3] 最终渲染的 remote_write ====="
kubectl -n $NS exec $CP -c prometheus -- sh -c \
  'awk "/^remote_write:/,/^[a-z_]+\$/" /etc/prometheus/config_out/prometheus.env.yaml' 2>&1
echo
echo "===== [4] 队列健康 ====="
for m in prometheus_remote_storage_samples_pending prometheus_remote_storage_samples_total prometheus_remote_storage_shards; do
  printf '  %-46s ' "$m"
  kubectl -n $NS exec $CP -c prometheus -- wget -qO- "http://localhost:9090/api/v1/query?query=$m" 2>/dev/null | python3 -c "
import sys,json
try:
  r=json.load(sys.stdin)['data']['result']; print(r[0]['value'][1] if r else '0')
except: print('ERR')"
done
