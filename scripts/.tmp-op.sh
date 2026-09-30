#!/bin/bash
echo "=== helper: operator image ==="
grep -rn "operator" /tmp/cilchart/cilium/templates/_helpers.tpl | head -20
echo "=== harbor operator tags ==="
curl -sk -u admin:'<HARBOR_PASSWORD>' 'https://harbor.wuxing.local/v2/cilium/operator/tags/list'
echo; echo "=== harbor operator-generic repo ==="
curl -sk -u admin:'<HARBOR_PASSWORD>' 'https://harbor.wuxing.local/v2/cilium/operator-generic/tags/list'
echo; echo "=== unified values operator block ==="
grep -n -B3 -A6 'harbor.wuxing.local/cilium/operator' /data1/ssdxt/values/cilium-values-unified.yaml