#!/bin/bash
echo '== 422 错误详情 =='
grep -aB6 'admin/users HTTP/1.0" 422' /ManualAI/OmniKnow/logs/aiserver.log 2>/dev/null | sed -e 's/\x1b\[[0-9;]*m//g' | grep -aE '错误详情|type|loc|msg|missing|input|路由' | tail -14
