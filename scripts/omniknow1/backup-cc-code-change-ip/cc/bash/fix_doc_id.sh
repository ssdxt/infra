#!/bin/bash
# =============================================================================
# file_doc.doc_id 回填工具 —— 修复「问答对/试题生成失败」
# -----------------------------------------------------------------------------
# 【症状】
#   前端知识库页面点「生成题库」后提示失败；knowledge_file.qa_status = 失败。
#   后端日志（/deploy/cc/logs/api_log.txt）出现：
#       OPTIONS /train/generate_test_cases 200 OK
#       []                                  <-- print(chunks)，空列表
#       POST    /train/generate_test_cases 200 OK
#   解析阶段另有若干行：未找到匹配的记录，无法更新 doc_id
#
# 【根因】
#   server/db/repository/knowledge_file_repository.py 的 update_docs_in_db()
#   用「metadata key 集合完全相等」定位记录，但向量化时 embed_documents()
#   给 doc.metadata 追加了 "id" 键，DB 里存的是解析阶段（无 "id"）的 metadata，
#   键集合永远不相等 -> doc_id 永远不回填 -> file_doc.doc_id 全为 NULL。
#   随后 KBService.list_docs() 用 doc_id=NULL 调 get_doc_by_id(None) 全部返回 None，
#   list_docs() 返回 []，generate_test_cases() 判为「未找到文档块」并置 qa_status=失败。
#
#   代码修复（key 子集匹配 + 匹配后消费）已应用到：
#       server/db/repository/knowledge_file_repository.py
#   备份：同目录 .bak-docid-20260918
#   本脚本负责把**历史遗留**的 NULL doc_id 按向量库实际内容回填。
#
# 【用法】
#   ./fix_doc_id.sh diag          [kb_name]   # 体检：每个知识库有多少 NULL / 能否匹配
#   ./fix_doc_id.sh fix           [kb_name]   # 试运行，只打印不写库
#   ./fix_doc_id.sh fix --apply   [kb_name]   # 真正写库，并在 /deploy/cc/logs 留回滚文件
#   ./fix_doc_id.sh verify        [kb_name]   # 校验 doc_id 是否与向量库对齐
#   ./fix_doc_id.sh rollback      [kb_name]   # 用最近一次回滚文件还原
#
#   kb_name 省略 = 处理全部知识库。
#
# 【修复后必须做】
#   systemctl restart chat_doc_api          # 让改过的 repository 生效
#   然后到前端重新点「生成题库」，或：
#   curl -k -X POST https://192.168.21.111:8261/train/generate_test_cases \
#        -H 'Content-Type: application/json' -H "token: <JWT>" \
#        -d '{"kb_name":"testt","file_name":"<文件名>"}'
# =============================================================================

set -u

PY=/root/anaconda3/envs/recovery/bin/python
HERE="$(cd "$(dirname "$0")" && pwd)"
WORKER="$HERE/fix_doc_id.py"

if [ ! -f "$WORKER" ]; then
    echo "ERROR: worker not found: $WORKER" >&2
    exit 1
fi
if [ ! -x "$PY" ]; then
    echo "ERROR: python not found: $PY" >&2
    exit 1
fi

MODE="${1:-diag}"
shift || true

# 兼容 'fix --apply kb' 与 'fix kb --apply' 两种写法
ARGS=""
APPLY=""
KB=""
for a in "$@"; do
    case "$a" in
        --apply) APPLY="--apply" ;;
        *)       [ -z "$KB" ] && KB="$a" ;;
    esac
done

echo "=== fix_doc_id: mode=$MODE kb=${KB:-ALL} apply=${APPLY:-no} ==="
"$PY" "$WORKER" "$MODE" ${KB:+"$KB"} $APPLY
rc=$?
echo "=== done (rc=$rc) ==="
exit $rc
