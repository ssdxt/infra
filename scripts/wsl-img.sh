#!/bin/bash
WORK=/home/cc/charts
cd $WORK
echo "== kube-prometheus-stack 镜像"
helm template rel kube-prometheus-stack-62.7.0.tgz --namespace monitoring 2>/dev/null | grep -oE 'image: [^ ]+' | sed 's/image: //' | grep -vE '^\$|^-' | sort -u
echo "== cert-manager 镜像"
helm template cm cert-manager-v1.16.1.tgz --namespace cert-manager 2>/dev/null | grep -oE 'image: [^ ]+' | sed 's/image: //' | grep -vE '^\$|^-' | sort -u