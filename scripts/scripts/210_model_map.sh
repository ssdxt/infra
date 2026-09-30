#!/bin/bash
echo '===== 1. parser/rag/.env 模型地址键 ====='
grep -nE 'URL|BASE|HOST|API_KEY|MODEL|MINERU|PORT' /ManualAI/OmniKnow/omniknow2/parser/rag/.env 2>/dev/null | grep -vE '^[0-9]+:#' | head -25
echo
echo '===== 2. assistant/conf.yaml 的 LLM/模型段 ====='
grep -nE 'llm|LLM|model|base_url|api_key|openai|ollama|qwen|url|host|port' /ManualAI/OmniKnow/omniknow2/assistant/conf.yaml 2>/dev/null | grep -vE '^\s*#|:\s*#' | head -25
echo
echo '===== 3. assistant/.env ====='
cat /ManualAI/OmniKnow/omniknow2/assistant/.env 2>/dev/null | grep -vE '^\s*#|^$' | head -20
echo
echo '===== 4. speech/.env 模型地址 ====='
grep -nE 'URL|HOST|PORT|MODEL|ASR|TTS|KEY' /ManualAI/OmniKnow/omniknow2/speech/.env 2>/dev/null | head -15
echo
echo '===== 5. envs 模板(参考) ====='
for f in /ManualAI/OmniKnow/omniknow2/envs/.env-assistant /ManualAI/OmniKnow/omniknow2/envs/.env-server; do echo "-- $f"; grep -nE 'URL|HOST|MODEL|BASE' "$f" 2>/dev/null | head -10; done
echo
echo '===== 6. server 代码里 chat LLM 配置来源 ====='
grep -rnE 'llm_base|LLM_BASE|chat.*base|BASE_URL|MODEL_NAME|dashscope' /ManualAI/OmniKnow/omniknow2/server/core/config.py /ManualAI/OmniKnow/omniknow2/server/services/*.py /ManualAI/OmniKnow/omniknow2/server/ext/*.py 2>/dev/null | grep -vE '__pycache__|\.venv' | head -10
