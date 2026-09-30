#!/usr/bin/env bash
set -e

cd /ManualAI/OmniKnow/omniknow2/server

source /root/anaconda3/bin/activate aiserver

celery -A ext.celery_app:celery_app beat \
      --loglevel=info \
      -S redbeat.RedBeatScheduler  2>&1 | tee -a /ManualAI/OmniKnow/logs/celery_beat.log
