#!/bin/bash
echo "== BASIC_MODEL api_key line =="
grep -n 'api_key' /ManualAI/OmniKnow/omniknow2/assistant/conf.yaml | head -1
echo "== extract & count =="
v=$(grep 'api_key' /ManualAI/OmniKnow/omniknow2/assistant/conf.yaml | head -1 | sed 's/.*api_key: *"//; s/".*//')
echo "len=${#v}"
echo "value=[$v]"
