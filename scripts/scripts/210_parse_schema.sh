#!/bin/bash
echo '== DocParseRequest 定义 =='
grep -rnB3 -A25 'class DocParseRequest' /ManualAI/OmniKnow/omniknow2/server --include='*.py' 2>/dev/null | grep -vE '__pycache__|\.venv' | head -35
echo '== parse 路由处理(字段名) =='
grep -rnB2 -A15 'def parse_documents' /ManualAI/OmniKnow/omniknow2/server/api/endpoints/kbase.py 2>/dev/null | head -25
