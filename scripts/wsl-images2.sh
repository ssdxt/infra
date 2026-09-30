#!/bin/bash
WORK=/home/cc/charts; cd $WORK
echo "== 用 helm template 渲染并提取所有镜像"
helm template rel kube-prometheus-stack-62.7.0.tgz --namespace monitoring 2>/dev/null | grep -oE 'image: [^ ]+' | sed 's/image: //' | grep -vE '^\$|^- ' | sort -u
