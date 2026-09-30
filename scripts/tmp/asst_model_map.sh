#!/bin/bash
cd /ManualAI/OmniKnow/omniknow2/assistant
echo "== model key mapping in code =="
grep -rnE '"basic"|glm4_7_flash|qwen3_next_80b|deepseek-chat' src --include="*.py" 2>/dev/null | head -15
echo "== config model blocks usage =="
grep -rnE 'BASIC_MODEL|GLM4_7_FLASH_MODEL|DEEPSEEK_CHAT_MODEL' src --include="*.py" 2>/dev/null | head -15
echo "== chat endpoint + model param =="
grep -rnE 'def.*chat|model.*=|model_type|MODEL' src/server/app.py src/config/*.py 2>/dev/null | head -20
