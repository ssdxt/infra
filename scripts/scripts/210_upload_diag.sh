#!/bin/bash
echo '===== aiserver.log 最近 25 行 ====='
tail -25 /ManualAI/OmniKnow/logs/aiserver.log 2>/dev/null
echo
echo '===== parser.log 最近 10 行 ====='
tail -10 /ManualAI/OmniKnow/logs/parser.log 2>/dev/null
echo
echo '===== celery_worker.log 最近 10 行 ====='
tail -10 /ManualAI/OmniKnow/logs/celery_worker.log 2>/dev/null
