#!/bin/bash
# Zero-risk validation: build the candidate config and validate it inside a RUNNING alloy pod
export KUBECONFIG=/etc/kubernetes/admin.conf
CFG=/tmp/alloy-new-config.alloy
cat > $CFG <<'ALLOYEOF'
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
echo "=== candidate config written ($(wc -c < $CFG) bytes) ==="

POD=$(kubectl -n logging get pods -l app.kubernetes.io/name=alloy --no-headers | awk '{print $1}' | head -1)
echo "pod=$POD"
echo ""
echo "=== alloy CLI subcommands ==="
kubectl -n logging exec $POD -c alloy -- /bin/alloy --help 2>&1 | sed -n '/Available Commands/,/^Flags/p' | head -25

echo ""
echo "=== copy config into pod ==="
kubectl cp $CFG logging/$POD:/tmp/candidate.alloy -c alloy 2>&1 && echo "  copied"

echo ""
echo "=== try: alloy validate ==="
kubectl -n logging exec $POD -c alloy -- /bin/alloy validate /tmp/candidate.alloy 2>&1 | head -20
echo "  (exit=$?)"

echo ""
echo "=== try: alloy fmt --test (syntax check) ==="
kubectl -n logging exec $POD -c alloy -- /bin/alloy fmt --test /tmp/candidate.alloy 2>&1 | head -20
echo "  (exit=$?)"
