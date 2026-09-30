#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== 有没有工作负载用 node-role 做 nodeSelector（若有，混用标签会出问题）"
kubectl get pods -A -o json 2>/dev/null | python3 -c '
import sys, json
d = json.load(sys.stdin)
hits = 0
for p in d["items"]:
    spec = p["spec"]
    ns = p["metadata"]["namespace"]
    # nodeSelector
    sel = spec.get("nodeSelector") or {}
    for k, v in sel.items():
        if "node-role" in k:
            print("  nodeSelector:", ns, p["metadata"]["name"], "->", k, "=", repr(v)); hits += 1
    # affinity nodeAffinity
    aff = ((spec.get("affinity") or {}).get("nodeAffinity") or {})
    txt = json.dumps(aff)
    if "node-role" in txt:
        print("  nodeAffinity:", ns, p["metadata"]["name"]); hits += 1
if not hits:
    print("  没有任何工作负载用 node-role 标签做调度选择")
'
echo ""
echo "=== 各节点的污点（看 worker/control 是否可调度）"
kubectl get nodes -o custom-columns='NAME:.metadata.name,TAINTS:.spec.taints[*].key,UNSCHED:.spec.unschedulable'