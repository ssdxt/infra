#!/bin/bash
# 结论导向: 对比 plant01 与集群侧同一指标的"最新样本时间", 判断桶是否还在被推送
P=http://10.100.10.29:9091
export KUBECONFIG=/etc/kubernetes/admin.conf
CP=prometheus-prometheus-stack-kube-prom-prometheus-0
NS=monitoring

val() { # $1=url $2=query $3=exec-mode(k8s|curl)
  if [ "$3" = "k8s" ]; then
    kubectl -n $NS exec $CP -c prometheus -- wget -qO- --timeout=10 --header='Content-Type: application/x-www-form-urlencoded' "http://localhost:9090/api/v1/query?query=$2" 2>/dev/null
  else
    curl -s --get "$1/api/v1/query" --data-urlencode "query=$2"
  fi | python3 -c "
import sys,json,datetime
try:
  r=json.load(sys.stdin)['data']['result']
  if not r: print('无数据'); raise SystemExit
  v=float(r[0]['value'][1])
  print('%s  (%s)' % (r[0]['value'][1], datetime.datetime.utcfromtimestamp(v).strftime('%H:%M:%S UTC')))
except SystemExit: pass
except Exception as e: print('ERR',e)"
}

echo "===== 现在时间 ====="
date -u '+%H:%M:%S UTC  (epoch=%s)'

echo
echo "===== A. plant01 侧: 被 drop 的桶指标 最新样本时间 ====="
echo -n "  apiserver_request_duration_seconds_bucket : "; val "$P" 'max(timestamp(apiserver_request_duration_seconds_bucket))' curl
echo -n "  etcd_request_duration_seconds_bucket     : "; val "$P" 'max(timestamp(etcd_request_duration_seconds_bucket))' curl

echo
echo "===== B. plant01 侧: 正常推送的指标 最新样本时间(对照) ====="
echo -n "  apiserver_request_total                  : "; val "$P" 'max(timestamp(apiserver_request_total))' curl
echo -n "  node_cpu_seconds_total                   : "; val "$P" 'max(timestamp(node_cpu_seconds_total))' curl

echo
echo "===== C. 集群侧: 同一指标的最新时间(证明集群一直有新鲜数据) ====="
echo -n "  apiserver_request_duration_seconds_bucket : "; val "" 'max(timestamp(apiserver_request_duration_seconds_bucket))' k8s
echo -n "  apiserver_request_total                  : "; val "" 'max(timestamp(apiserver_request_total))' k8s

echo
echo "===== D. 判定 ====="
echo "  若 A 的时间 ~= patch 时刻(06:15) 且明显早于 B/C => 桶序列已停更(drop 生效),"
echo "  plant01 head 里只是 patch 前的历史残留, 会随 2h 块压缩/删除消失。"
