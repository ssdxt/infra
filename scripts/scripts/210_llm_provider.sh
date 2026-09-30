#!/bin/bash
echo '== conf.yaml 顶部结构(provider 名) =='
sed -n '1,30p' /ManualAI/OmniKnow/omniknow2/assistant/conf.yaml 2>/dev/null | grep -nE '^[a-z_]+:|provider|default|llm|model' | head -15
echo '== conf.yaml 20-30 行上下文 =='
sed -n '20,30p' /ManualAI/OmniKnow/omniknow2/assistant/conf.yaml 2>/dev/null
echo '== assistant 如何选 provider =='
grep -rnE 'llm_provider|LLM_PROVIDER|provider|active_llm|current_llm|get_llm|default_llm' /ManualAI/OmniKnow/omniknow2/assistant/src --include='*.py' 2>/dev/null | grep -vE '__pycache__|# ' | head -10
