#!/bin/bash
# 任务3-步骤1: 在 control-01 上把 PrometheusRule JSON 转成原生规则 yaml 并校验
export KUBECONFIG=/etc/kubernetes/admin.conf
set -e
cd /tmp

echo "===== [1] 导出 PrometheusRule(最新) ====="
kubectl -n monitoring get prometheusrule -o json > /tmp/cluster-rules-all.json
echo "  $(wc -c < /tmp/cluster-rules-all.json) bytes, $(python3 -c "import json;print(len(json.load(open('/tmp/cluster-rules-all.json'))['items']))") 个 PrometheusRule"

echo
echo "===== [2] 转换为原生规则文件 ====="
python3 /tmp/convert_rules.py /tmp/cluster-rules-all.json /tmp/cluster-wxq-rules.yaml

echo
echo "===== [3] 文件概况 ====="
wc -l /tmp/cluster-wxq-rules.yaml
echo "  前 25 行:"
head -25 /tmp/cluster-wxq-rules.yaml

echo
echo "===== [4] promtool 语法校验(在 control-01 上用容器里的 promtool) ====="
# 把 yaml 拷进一个临时容器校验
docker run --rm -v /tmp/cluster-wxq-rules.yaml:/rules.yaml:ro \
  harbor.wuxing.local/wxq-monitor/prometheus:v3.13.1 \
  promtool check rules /rules.yaml 2>&1 | tail -20 || \
  echo "  (本机无该镜像, 改到 plant01 校验)"
