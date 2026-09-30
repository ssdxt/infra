#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
P=prometheus-prometheus-stack-kube-prom-prometheus-0
echo "===== [1] 集群 Prometheus 规模(评估推到 plant01 的量) ====="
kubectl -n monitoring exec $P -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/status/tsdb' 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']
h=d['headStats']
print('  numSeries      =',h['numSeries'])
print('  numLabelPairs  =',h['numLabelPairs'])
print('  chunkCount     =',h['chunkCount'])
print()
print('  Top10 指标名(按 series 数):')
for x in d['seriesCountByMetricName'][:10]:
    print('    %-55s %s' % (x['name'],x['value']))
print()
print('  Top10 标签名:')
for x in d['labelValueCountByLabelName'][:10]:
    print('    %-40s %s' % (x['name'],x['value']))
"
echo
echo "===== [2] 各 job 的时序数(决定是否需要过滤) ====="
for j in apiserver coredns kube-controller-manager kube-scheduler kube-state-metrics kubelet node-exporter prometheus-stack-kube-prom-alertmanager prometheus-stack-kube-prom-operator prometheus-stack-kube-prom-prometheus; do
  n=$(kubectl -n monitoring exec $P -c prometheus -- wget -qO- "http://localhost:9090/api/v1/query?query=count(%7Bjob%3D%22$j%22%7D)" 2>/dev/null | python3 -c "import sys,json;r=json.load(sys.stdin)['data']['result'];print(r[0]['value'][1] if r else '?')" 2>/dev/null)
  printf '  %-45s %s\n' "$j" "$n"
done
echo
echo "===== [3] plant01 当前规模(remote_write 前基线) ====="
ssh_head=0
echo "  (在 plant01 上执行)"
echo
echo "===== [4] 集群 Prometheus 当前是否已有 remoteWrite ====="
kubectl -n monitoring get prometheus prometheus-stack-kube-prom-prometheus -o jsonpath='{.spec.remoteWrite}' ; echo "(空=未配置)"
echo
echo "===== [5] 集群 prometheus 到 plant01 的连通性复测 ====="
kubectl -n monitoring exec $P -c prometheus -- wget -qO- --timeout=8 'http://10.100.10.29:9091/api/v1/status/runtimeinfo' 2>&1 | head -c 200; echo
echo -n "  从集群 Pod 内 POST /api/v1/write 期望 400 => "
kubectl -n monitoring exec $P -c prometheus -- wget -qO- --timeout=8 --post-data='' 'http://10.100.10.29:9091/api/v1/write' 2>&1 | head -c 300; echo
