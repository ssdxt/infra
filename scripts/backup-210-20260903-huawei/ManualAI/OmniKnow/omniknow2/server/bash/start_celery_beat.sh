#!/usr/bin/env bash
set -e

export PATH=/root/anaconda3/envs/aiserver/bin:$PATH

cd /aiserverspace

source /root/anaconda3/bin/activate aiserver

celery -A ext.celery_app:celery_app beat \
      --loglevel=info \
      -S redbeat.RedBeatScheduler
