#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== 1. ruler 是否启用（loki ConfigMap）==="
kubectl -n logging get cm loki -o jsonpath='{.data.loki\.yaml}' 2>/dev/null | grep -B1 -A6 "^ruler:" | sed 's/^/  /' || echo "  无 ruler 段"
echo ""
echo "=== 2. helm values 里的 ruler 段 ==="
grep -B2 -A8 "ruler" /data1/ssdxt/values/loki-values.yaml 2>/dev/null | head -25 | sed 's/^/  /' || { echo "  找 values 文件:"; ls /data1/ssdxt/values/ | grep -i loki; }
echo ""
echo "=== 3. 规则 ConfigMap / 目录 ==="
kubectl -n logging get cm --no-headers 2>/dev/null | grep -iE "ruler|rule" | sed 's/^/  /' || echo "  无规则 CM"
kubectl -n logging exec loki-0 -c loki -- ls /rules 2>/dev/null | sed 's/^/  /rules: /' || true
echo ""
echo "=== 4. Ruler API 现状（当前生效的规则组）==="
kubectl -n logging exec loki-0 -c loki -- wget -qO- http://localhost:3100/loki/api/v1/rules 2>/dev/null | head -c 400; echo ""
echo ""
echo "=== 5. 五件套子智能体的产出文件检查 ==="
ls -la /data1/ssdxt/monitoring/ 2>/dev/null | grep -iE "ruler|loki-rule" | sed 's/^/  /'
ls -la /data1/ssdxt/logging/ 2>/dev/null | grep -iE "ruler|rule" | sed 's/^/  /'
find /data1/ssdxt -name "*ruler*" -o -name "*loki-rule*" 2>/dev/null | sed 's/^/  /'