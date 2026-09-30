#!/bin/bash
# 假设: remote_write 的 writeRelabelConfigs 对【抓取来的指标】生效,
#       但对 Prometheus【自身生成的指标】(ALERTS / 记录规则输出 / *_bucket
#       由记录规则产生) 不生效 —— 因为后者是 rule manager 直接写 TSDB+远端。
P=http://10.100.10.29:9091
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=monitoring; CP=prometheus-prometheus-stack-kube-prom-prometheus-0
q() { curl -s --get "$P/api/v1/query" --data-urlencode "query=$1"; }

echo "===== 验证: 已有的 drop 规则对哪些指标生效过 ====="
echo
echo "--- A. kubernetes_feature_enabled: 集群侧是否有 ---"
kubectl -n $NS exec $CP -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/query?query=count(kubernetes_feature_enabled)' 2>/dev/null | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print('    集群侧 =',r[0]['value'][1] if r else '0 (集群自己就没有该指标!)')"
echo "    plant01 侧 = $(q 'count(kubernetes_feature_enabled)' | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result'];print(r[0]['value'][1] if r else 0)")"
echo "    ^ 若集群侧本来就是 0, 那"drop 生效"是假象 —— 它根本没被推过"
echo
echo "--- B. 抓取类指标现状(证明 keep 规则生效) ---"
for m in node_cpu_seconds_total apiserver_request_total kube_node_info; do
  c=$(kubectl -n $NS exec $CP -c prometheus -- wget -qO- "http://localhost:9090/api/v1/query?query=count($m)" 2>/dev/null | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result'];print(r[0]['value'][1] if r else 0)")
  p=$(q "count($m{prometheus=~\"monitoring/.*\"})" | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result'];print(r[0]['value'][1] if r else 0)")
  printf '    %-28s 集群=%-8s plant01(远程来源)=%-8s %s\n' "$m" "$c" "$p" "$([ "$c" = "$p" ] && echo '一致(抓取类正常推送)' || echo '不一致')"
done
echo
echo "--- C. 生成类指标: 是否也被推(不受 drop 影响) ---"
for m in ALERTS count:up1; do
  c=$(kubectl -n $NS exec $CP -c prometheus -- wget -qO- "http://localhost:9090/api/v1/query?query=count($m)" 2>/dev/null | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result'];print(r[0]['value'][1] if r else 0)")
  p=$(q "count($m{prometheus=~\"monitoring/.*\"})" | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result'];print(r[0]['value'][1] if r else 0)")
  printf '    %-28s 集群=%-8s plant01(远程来源)=%-8s\n' "$m" "$c" "$p"
done
echo
echo "===== 结论判据 ====="
echo "  若 B 一致(抓取类在推) 且 C 中 ALERTS/count:up1 仍在被推 =>"
echo "  说明 writeRelabelConfigs 只作用于抓取样本, 对生成指标无效。"
echo
echo "===== 附: 集群侧 ALERTS 数量(用于对照) ====="
kubectl -n $NS exec $CP -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/query?query=count(ALERTS)' 2>/dev/null | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print('  集群 ALERTS 序列 =',r[0]['value'][1] if r else 0)"
echo
echo "===== 最近 5 分钟 out-of-order 统计 ====="
docker logs wxq-prometheus --since 5m 2>&1 | grep -c 'Out of order sample'
docker logs wxq-prometheus --since 5m 2>&1 | grep 'Out of order sample' | grep -o '__name__=\\"[^"\\]*\\"' | sed 's/__name__=\\"//; s/\\"//' | sort | uniq -c | sort -rn
