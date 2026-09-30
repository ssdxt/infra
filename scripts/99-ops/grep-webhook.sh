#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
kubectl -n kyverno get jobs,pods | grep -i migrat
for j in $(kubectl -n kyverno get jobs -o name | grep migrat); do
  kubectl -n kyverno get $j -o jsonpath="{$j} {.spec.template.spec.containers[0].image}{'\n'}"
done
