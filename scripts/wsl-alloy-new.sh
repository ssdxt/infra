#!/bin/bash
# 在 WSL 里先渲染新 values，确认 volumes / env / configmap 都正确，再上集群
set -u
C=/tmp/dsh-charts
[ -f $C/alloy-0.12.0.tgz ] || { echo "chart missing in WSL"; exit 1; }
D=/tmp/alloy-new; mkdir -p $D

cat > $D/alloy-custom-new.yaml <<'YAML'
alloy:
  mounts:
    varlog: true
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
  resources:
    requests: {cpu: 100m, memory: 256Mi}
    limits: {memory: 1Gi}
controller:
  type: daemonset
  tolerations:
  - operator: Exists
configReloader:
  enabled: false
YAML

# 用上一轮已经验证过的镜像改写 values
python3 /mnt/c/Users/CC/Desktop/dsh/fix-chart-images-v2.py $C/alloy-0.12.0.tgz logging harbor.wuxing.local $D/alloy-harbor.yaml

echo "=== render ==="
helm template alloy $C/alloy-0.12.0.tgz -n logging -f $D/alloy-harbor.yaml -f $D/alloy-custom-new.yaml > $D/render.yaml 2>$D/render.err || cat $D/render.err
echo "--- images ---"
grep -E '^\s+-?\s*image:' $D/render.yaml | sed 's/.*image: *//' | tr -d '"' | sort -u
echo "--- volumes ---"
python3 - <<'PY'
import yaml
d=[x for x in yaml.safe_load_all(open('/tmp/alloy-new/render.yaml')) if x]
for doc in d:
    if doc.get('kind')=='DaemonSet':
        sp=doc['spec']['template']['spec']
        print("  containers:", [c['name'] for c in sp['containers']])
        for c in sp['containers']:
            print("   env:", c.get('env'))
            print("   mounts:", c.get('volumeMounts'))
        print("  volumes:", sp.get('volumes'))
        print("  hostNetwork:", sp.get('hostNetwork'), "dnsPolicy:", sp.get('dnsPolicy'))
PY
echo "--- configmap content sanity ---"
python3 - <<'PY'
import yaml
d=[x for x in yaml.safe_load_all(open('/tmp/alloy-new/render.yaml')) if x]
for doc in d:
    if doc.get('kind')=='ConfigMap':
        for k,v in (doc.get('data') or {}).items():
            print(f"  [{doc['metadata']['name']}] key={k} len={len(v)}")
            print("  first line:", v.strip().splitlines()[0] if v.strip() else "")
PY
