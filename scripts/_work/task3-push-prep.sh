#!/bin/bash
# 在 control-01 上把生成好的规则文件搬到 plant01
set -e
echo "===== 源文件(control-01) ====="
ls -la /tmp/cluster-wxq-rules.yaml
md5sum /tmp/cluster-wxq-rules.yaml
echo
echo "  (由工作站中转 scp 到 plant01, 见后续步骤)"
