#!/bin/bash
# 验证加 stage.cri {} 后的配置（在运行中的 alloy pod 里用 alloy run 试跑）
export KUBECONFIG=/etc/kubernetes/admin.conf
POD=$(kubectl -n logging get pods -l app.kubernetes.io/name=alloy --no-headers | awk '{print $1}' | head -1)
echo "pod=$POD"
cat > /tmp/cri-test.alloy <<'ALLOYEOF'
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
  stage.cri {}
  stage.regex {
    expression = "/var/log/pods/(?P<namespace>[^_]+)_(?P<pod>[^_]+)_(?P<pod_uid>[^/]+)/(?P<container>[^/]+)/.*"
  }
  stage.labels {
    values = {
      namespace = "",
      pod       = "",
      container = "",
    }
  }
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
ALLOYEOF
kubectl cp /tmp/cri-test.alloy logging/$POD:/tmp/cri-test.alloy -c alloy 2>&1 && echo "  copied"
echo "=== alloy run with stage.cri (expect clean load, no config error) ==="
kubectl -n logging exec $POD -c alloy -- sh -c 'timeout 12 /bin/alloy run --server.http.listen-addr=127.0.0.1:12400 --storage.path=/tmp/alloy-cri-test /tmp/cri-test.alloy 2>&1 | grep -iE "level=error|error|finished complete graph|scheduling loaded|node exited" | head -12'
echo "  (done)"
