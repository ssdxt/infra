#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== kubectl get nodes 的 ROLES 列"
kubectl get nodes
echo ""
echo "=== 原始节点 wxq-run-07 的标签"
kubectl get node wxq-run-07 -o jsonpath='{.metadata.labels}' | python3 -m json.tool 2>/dev/null
echo ""
echo "=== 新加入节点 wxq-run-08 的标签"
kubectl get node wxq-run-08 -o jsonpath='{.metadata.labels}' | python3 -m json.tool 2>/dev/null
echo ""
echo "=== 对照：控制节点 wxq-control-01 的标签"
kubectl get node wxq-control-01 -o jsonpath='{.metadata.labels}' | python3 -m json.tool 2>/dev/null
echo ""
echo "=== 全集群谁带 worker 标签"
kubectl get nodes -o json | python3 -c '
import sys,json
d=json.load(sys.stdin)
for n in d["items"]:
    labels=n["metadata"].get("labels",{})
    w=labels.get("node-role.kubernetes.io/worker")
    cp=labels.get("node-role.kubernetes.io/control-plane")
    print(f"  {n[\"metadata\"][\"name\"]:22s} worker={w!r:8s} control-plane={cp!r}")
'
echo ""
echo "=== 节点创建时间对比（看谁是什么时候进来的）"
kubectl get nodes -o json | python3 -c '
import sys,json
d=json.load(sys.stdin)
for n in d["items"]:
    print(f"  {n[\"metadata\"][\"name\"]:22s} created={n[\"metadata\"][\"creationTimestamp\"]}")
'