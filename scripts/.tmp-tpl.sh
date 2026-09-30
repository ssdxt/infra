#!/bin/bash
grep -rn "operator" /tmp/cilchart/cilium/templates/cilium-operator/deployment.yaml | grep -iE "image|suffix|generic" 
echo ===
grep -rn -A10 "define cilium.operator.image" /tmp/cilchart/cilium/templates/_helpers.tpl /tmp/cilchart/cilium/templates/cilium-operator/*.yaml 2>/dev/null | head -20
grep -rln "operator.image" /tmp/cilchart/cilium/templates/_helpers.tpl
grep -rn -B2 -A12 "operator.image\b" /tmp/cilchart/cilium/templates/_helpers.tpl | head -30