#!/bin/bash
echo "== find model list in frontend =="
grep -rl "Gnosis" /ManualAI/OmniKnow/data/nginx/html/omniknow/ 2>/dev/null | head -5
echo "== extract model select config =="
f=$(grep -rl "Gnosis" /ManualAI/OmniKnow/data/nginx/html/omniknow/assets/*.js /ManualAI/OmniKnow/data/nginx/html/omniknow/js/*.js 2>/dev/null | head -1)
echo "FILE=$f"
if [ -n "$f" ]; then
  grep -oE '.{40}Gnosis.{160}' "$f" 2>/dev/null | head -6
fi
echo "== model name mapping (value) =="
grep -rhoE '(Gnosis 1.0-35B|Gnosis 1.0-13B|Gnosis 1.0-9B|glm-5.1|GLM[^", ]*)[^,;]{0,60}' /ManualAI/OmniKnow/data/nginx/html/omniknow/assets/*.js 2>/dev/null | sort -u | head -25
