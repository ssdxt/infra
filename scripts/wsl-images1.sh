#!/bin/bash
WORK=/home/cc/charts
cd $WORK
echo "== 解压 kube-prometheus-stack 提取镜像"
rm -rf kps; mkdir kps; tar xzf kube-prometheus-stack-62.7.0.tgz -C kps
grep -rhoE 'repository: [^ ]+|image: [^ ]+' kps/ | sed -E 's/(repository|image): //' | grep -vE '^\{|\$\{|grafana-sys|'"'"'|\}' | sort -u | head -40
