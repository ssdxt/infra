#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
kubectl -n kube-system patch deploy cilium-operator --type json -p '[{"op":"replace","path":"/spec/template/spec/containers/0/command/0","value":"cilium-operator"}]'
kubectl -n kube-system logs cilium-sq6z6 -c cilium-agent --previous --tail=40 2>/dev/null || kubectl -n kube-system logs cilium-sq6z6 -c cilium-agent --tail=40