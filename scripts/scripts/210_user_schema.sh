#!/bin/bash
echo '== 找包含 role_ids 的创建用户 schema =='
grep -rln 'role_ids' /ManualAI/OmniKnow/omniknow2/server/schemas/*.py 2>/dev/null | head -5
F=$(grep -rln 'role_ids' /ManualAI/OmniKnow/omniknow2/server/schemas/*.py 2>/dev/null | grep -iE 'user|member|admin' | head -1)
[ -z "$F" ] && F=$(grep -rln 'role_ids' /ManualAI/OmniKnow/omniknow2/server/schemas/*.py 2>/dev/null | head -1)
echo "schema file: $F"
grep -nB5 -A25 'role_ids' "$F" 2>/dev/null | head -45
