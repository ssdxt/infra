#!/bin/bash
# =============================================================================
# 重新触发知识库「试题/问答对生成」并等待结果
# -----------------------------------------------------------------------------
# 前置条件：
#   1) 已执行修复：/deploy/cc/bash/fix_doc_id.sh fix --apply <kb_name>
#      （file_doc.doc_id 回填；否则 generate_test_cases 会报「未找到文档块」）
#   2) chat_doc_api 已重启（让 update_docs_in_db 的修复代码生效）
#      systemctl restart chat_doc_api
#   3) 大模型服务在线：GLM-4 @ http://192.168.21.111:10006/v1
#      （configs/model_config.py 的 GENERATE_MODEL_SERVER）
#
# 用法：
#   ./regen_qa.sh <kb_name> <file_name>
#   例：./regen_qa.sh testt "AIDT工业多智能体开放平台—开发阶段性技术验证报告.pdf"
#
# 说明：登录默认 admin / Abcd1234，可用环境变量 REGEN_USER / REGEN_PASSWORD 覆盖。
# =============================================================================

set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
PY=/root/anaconda3/envs/recovery/bin/python

if [ $# -lt 2 ]; then
    echo "usage: $0 <kb_name> <file_name>" >&2
    exit 2
fi
KB="$1"
FILE="$2"
USER="${REGEN_USER:-admin}"
PASS="${REGEN_PASSWORD:-Abcd1234}"

echo "=== regen_qa: kb=$KB user=$USER ==="
"$PY" "$HERE/regen_qa.py" "$KB" "$FILE" --user "$USER" --password "$PASS"
rc=$?
echo "=== regen_qa done (rc=$rc) ==="
exit $rc
