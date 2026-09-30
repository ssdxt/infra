#!/bin/bash
set -u
C=/tmp/dsh-charts
echo "############ ALLOY top-level keys ############"
python3 - <<'PY'
import yaml
v=yaml.safe_load(open('/tmp/alloy-values.yaml'))
def show(d, pre=''):
    for k,val in d.items():
        if isinstance(val,dict):
            print(f"{pre}{k}: <dict> keys={list(val.keys())[:12]}")
        else:
            print(f"{pre}{k}: {str(val)[:70]}")
show(v)
PY

echo ""
echo "############ ALLOY images rendered with script values ############"
cat > /tmp/alloy-custom.yaml <<'YAML'
alloy:
  configMap:
    create: true
    content: |
      // test
      loki.write "default" {
        endpoint { url = "http://loki.logging.svc.cluster.local:3100/loki/api/v1/push" }
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
helm template alloy $C/alloy-0.12.0.tgz -n logging -f /tmp/alloy-custom.yaml > /tmp/alloy-render.yaml 2>/tmp/alloy-render.err || { echo "TEMPLATE FAILED:"; cat /tmp/alloy-render.err; }
echo "--- images ---"
grep -n -E '^\s+image:' /tmp/alloy-render.yaml
echo "--- does rendered config contain our test string? ---"
grep -c 'loki.write "default"' /tmp/alloy-render.yaml
echo "--- configmap names ---"
grep -n -A3 'configMap' /tmp/alloy-render.yaml | grep -E 'kind: ConfigMap|  name:' | head
echo "--- err ---"; cat /tmp/alloy-render.err

echo ""
echo "############ LOKI images rendered with script values ############"
cat > /tmp/loki-custom.yaml <<'YAML'
deploymentMode: SingleBinary
loki:
  auth_enabled: false
  commonConfig:
    replication_factor: 1
  storage:
    type: filesystem
  limits_config:
    retention_period: 168h
    ingestion_rate_mb: 16
    ingestion_burst_size_mb: 32
  schemaConfig:
    configs:
    - from: "2024-01-01"
      store: tsdb
      object_store: filesystem
      schema: v13
      index: {prefix: loki_index_, period: 24h}
singleBinary:
  replicas: 1
  persistence:
    enabled: true
    size: 50Gi
    storageClass: longhorn
  resources:
    requests: {cpu: 200m, memory: 512Mi}
    limits: {memory: 2Gi}
backend: {replicas: 0}
read: {replicas: 0}
write: {replicas: 0}
gateway: {enabled: false}
chunksCache: {enabled: false}
resultsCache: {enabled: false}
lokiCanary: {enabled: false}
test: {enabled: false}
minio: {enabled: false}
YAML
helm template loki $C/loki-6.24.0.tgz -n logging -f /tmp/loki-custom.yaml > /tmp/loki-render.yaml 2>/tmp/loki-render.err || { echo "TEMPLATE FAILED:"; cat /tmp/loki-render.err; }
echo "--- all images (unique) ---"
grep -E '^\s+-?\s*image:' /tmp/loki-render.yaml | sed 's/.*image: *//' | tr -d '"' | sort -u
echo "--- kinds/names ---"
grep -E '^kind: |^  name: ' /tmp/loki-render.yaml | head -60
echo "--- services with ports ---"
python3 - <<'PY'
import yaml,sys
docs=[d for d in yaml.safe_load_all(open('/tmp/loki-render.yaml')) if d]
for d in docs:
    if d.get('kind')=='Service':
        print("SVC", d['metadata']['name'], [(p.get('name'),p.get('port'),p.get('targetPort')) for p in d['spec']['ports']])
    if d.get('kind')=='StatefulSet':
        print("STS", d['metadata']['name'], "replicas", d['spec'].get('replicas'))
    if d.get('kind')=='Deployment':
        print("DEP", d['metadata']['name'], "replicas", d['spec'].get('replicas'))
print("--- total docs:", len(docs))
PY
echo "--- err ---"; cat /tmp/loki-render.err
