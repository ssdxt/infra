#!/bin/bash
line=$(grep 'api_key:' /ManualAI/OmniKnow/omniknow2/assistant/conf.yaml | grep -v '#' | head -1)
echo "rawline=[$line]"
v=$(echo "$line" | sed 's/.*api_key: *"//; s/".*//')
echo "len=${#v}"
echo "value=[$v]"
