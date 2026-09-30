#!/bin/bash
cd /tmp && rm -rf cilchart && mkdir cilchart && tar xzf /data1/ssdxt/charts/cilium-1.20.1.tgz -C cilchart
echo "=== useDigest keys ==="
grep -n "useDigest" cilchart/cilium/values.yaml | head -20
echo "=== generic suffix ==="
grep -rn "generic" cilchart/cilium/values.yaml | head
grep -rn "operatorGeneric\|imageSuffix\|-generic" cilchart/cilium/templates/_helpers.tpl | head
echo "=== operator image block ==="
grep -n -B2 -A8 "^operator:" cilchart/cilium/values.yaml | head -30
echo "=== envoy useDigest ==="
grep -n -A5 "cilium-envoy" cilchart/cilium/values.yaml | head -20