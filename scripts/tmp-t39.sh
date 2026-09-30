#!/bin/bash
# FIX: stage.regex must read the `filename` label (the path), not the log line content.
set -u
export KUBECONFIG=/etc/kubernetes/admin.conf
F=/data1/ssdxt/logging/02-alloy.sh

cat > /tmp/cand2.alloy <<'ALLOYEOF'
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
  // containerd 写的是 CRI 格式 "<ts> stdout|stderr F <msg>"，先剥掉
  stage.cri {}
  // 关键: source = "filename"，从文件路径解析标签（不能用日志行内容，
  // 否则日志正文里提到别的 pod 路径时会打错标签）
  stage.regex {
    source     = "filename"
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

POD=$(kubectl -n logging get pods -l app.kubernetes.io/name=alloy --no-headers | awk '{print $1}' | head -1)
echo "=== [1] validate candidate in pod $POD ==="
kubectl cp /tmp/cand2.alloy logging/$POD:/tmp/cand2.alloy -c alloy 2>&1 | tail -1
OUT=$(kubectl -n logging exec $POD -c alloy -- sh -c 'timeout 12 /bin/alloy run --server.http.listen-addr=127.0.0.1:12401 --storage.path=/tmp/alloy-c2 /tmp/cand2.alloy' 2>&1)
echo "$OUT" | grep -iE 'level=error|Error:|cannot|unknown|invalid' | grep -v 'failed to start reporter' | head -8
if echo "$OUT" | grep -iE 'level=error|Error:|cannot|unknown|invalid' | grep -qv 'failed to start reporter'; then
  echo "  !! VALIDATION FAILED - aborting"
  exit 1
fi
echo "$OUT" | grep -E 'finished complete graph|scheduling loaded' | head -2
echo "  validation OK -> applying"

echo ""
echo "=== [2] patch script + helm upgrade ==="
TS=$(date +%m%d-%H%M%S)
cp -a $F $F.bak.$TS && echo "  backup: $F.bak.$TS"
python3 - <<'PY'
p='/data1/ssdxt/logging/02-alloy.sh'
s=open(p,encoding='utf-8').read()
old='''        stage.regex {
          expression = "/var/log/pods/(?P<namespace>[^_]+)_(?P<pod>[^_]+)_(?P<pod_uid>[^/]+)/(?P<container>[^/]+)/.*"
        }'''
new='''        stage.regex {
          // 关键: source="filename" —— 从文件路径解析，而不是日志行内容
          source     = "filename"
          expression = "/var/log/pods/(?P<namespace>[^_]+)_(?P<pod>[^_]+)_(?P<pod_uid>[^/]+)/(?P<container>[^/]+)/.*"
        }'''
if 'source     = "filename"' in s:
    print('  already fixed')
elif old in s:
    open(p,'w',encoding='utf-8').write(s.replace(old,new,1)); print('  patched stage.regex source')
else:
    print('  ANCHOR NOT FOUND'); raise SystemExit(1)
PY
bash -n $F && echo "  bash syntax OK"
bash $F 2>&1 | tail -4

echo ""
echo "=== [3] force rollout (ConfigMap change alone does not restart pods) ==="
kubectl -n logging rollout restart ds/alloy
kubectl -n logging rollout status ds/alloy --timeout=420s 2>&1 | tail -2
kubectl -n logging get ds alloy

echo ""
echo "=== [4] wait 120s for logs to land ==="
sleep 120
echo "--- new-CONNECT rate (expect ~0 if Alloy no longer uses pods/log) ---"
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/query?query=sum(rate(apiserver_request_total%7Bresource%3D%22pods%22%2Csubresource%3D%22log%22%2Cverb%3D%22CONNECT%22%7D%5B2m%5D))' 2>&1 | head -c 200
