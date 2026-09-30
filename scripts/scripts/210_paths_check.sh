#!/bin/bash
echo '===== paths.py 关键函数 ====='
grep -nE 'def |BUCKET|bucket|public' /ManualAI/OmniKnow/omniknow2/server/storage/paths.py 2>/dev/null | head -30
echo
echo '===== split_namespace 实现 ====='
sed -n '1,80p' /ManualAI/OmniKnow/omniknow2/server/storage/paths.py 2>/dev/null | head -80
