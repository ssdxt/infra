#!/bin/bash
line=$(grep -E '^[[:space:]]*api_key:' /ManualAI/OmniKnow/omniknow2/assistant/conf.yaml | head -1)
echo "line=[$line]"
v=$(echo "$line" | sed 's/.*api_key: *"//; s/".*//')
echo "len=${#v}"
