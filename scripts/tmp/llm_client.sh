#!/bin/bash
echo "== LLM client code in assistant =="
docker exec assistant sh -c 'grep -rn "chat.completions.create\|AsyncOpenAI\|OpenAI(" /app/src --include="*.py" 2>/dev/null | head -8'
docker exec assistant sh -c 'grep -rn "base_url" /app/src --include="*.py" 2>/dev/null | grep -ivE "test|#" | head -8'
