#!/bin/bash
# 部署 Alloy（DaemonSet，采集所有节点/Pod 日志发给 Loki）
# 采集方式: 读取宿主机 /var/log/pods（文件采集，不经 apiserver）
#   —— 不能用 loki.source.kubernetes: 它会为每个容器开一条 apiserver pods/log
#      CONNECT 长连接（实测 ~900 条），把 apiserver 压到 leader-election 失租。
# 前置: chart 已开 alloy.mounts.varlog=true（hostPath /var/log -> /var/log, readOnly）
#       并注入 NODE_NAME（fieldRef spec.nodeName）作为 node 标签
set -e
export KUBECONFIG=/etc/kubernetes/admin.conf
R=/data1/ssdxt; H=harbor.wuxing.local; NS=logging

python3 $R/tools/fix-chart-images.py $R/charts/alloy-0.12.0.tgz logging $H /tmp/alloy-values-harbor.yaml

# Alloy 配置：文件采集容器日志 → 推 Loki
# 注意1: local.file_match 的 path_targets 必须给 __path__
# 注意2: 标签由文件路径解析（/var/log/pods/<ns>_<pod>_<uid>/<container>/<n>.log）
# 注意3: node 标签来自 DaemonSet 注入的 NODE_NAME 环境变量
cat > /tmp/alloy-custom.yaml <<'YAML'
alloy:
  # 挂载宿主机 /var/log，才能读到 /var/log/pods
  mounts:
    varlog: true
  # 本节点名，作为 node 标签
  extraEnv:
  - name: NODE_NAME
    valueFrom:
      fieldRef:
        fieldPath: spec.nodeName
  configMap:
    create: true
    content: |
      // ---- 采集本节点所有容器日志（读宿主机 /var/log/pods，不经 apiserver）----
      local.file_match "pods" {
        path_targets = [{
          __path__ = "/var/log/pods/*/*/*.log",
          job      = "pods",
        }]
      }

      loki.source.file "pods" {
        targets    = local.file_match.pods.targets
        forward_to = [loki.process.pods.receiver]
      }

      loki.process "pods" {
        // containerd 写的是 CRI 格式: "<ts> stdout|stderr F <msg>"
        // 必须先用 cri 阶段剥掉前缀，否则日志行会带上时间戳和 stdout F
        stage.cri {}
        // 从文件路径解析 namespace / pod / pod_uid / container
        stage.regex {
          // 关键: source="filename" —— 从文件路径解析，而不是日志行内容
          source     = "filename"
          expression = "/var/log/pods/(?P<namespace>[^_]+)_(?P<pod>[^_]+)_(?P<pod_uid>[^/]+)/(?P<container>[^/]+)/.*"
        }
        // 提升为 Loki 流标签
        stage.labels {
          values = {
            namespace = "",
            pod       = "",
            container = "",
          }
        }
        // 本节点名
        stage.static_labels {
          values = {
            node = sys.env("NODE_NAME"),
          }
        }
        forward_to = [loki.write.default.receiver]
      }

      loki.write "default" {
        endpoint {
          url = "http://loki.logging.svc.cluster.local:3100/loki/api/v1/push"
        }
      }
  resources:
    requests: {cpu: 100m, memory: 256Mi}
    limits: {memory: 1Gi}
controller:
  type: daemonset
  tolerations:
  - operator: Exists
# 关掉 config-reloader sidecar（其镜像未搬入 Harbor；Alloy 自身会热加载 config）
configReloader:
  enabled: false
YAML

helm upgrade --install alloy $R/charts/alloy-0.12.0.tgz -n $NS \
  -f /tmp/alloy-values-harbor.yaml -f /tmp/alloy-custom.yaml --timeout 15m 2>&1 | tail -5

echo ""
echo "验证:"
echo "  kubectl -n logging get ds alloy                 # 期望 11/11"
echo "  kubectl -n logging get ds alloy -o jsonpath='{.spec.template.spec.volumes}'"
echo "  kubectl -n logging exec loki-0 -c loki -- wget -qO- http://localhost:3100/loki/api/v1/labels"
echo "  在 Grafana Explore 里查: {namespace=\"longhorn-system\"}"
