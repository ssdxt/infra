#!/usr/bin/env bash
set -e

cd /ManualAI/OmniKnow/omniknow2/server

source /root/anaconda3/bin/activate aiserver

celery -A ext.celery_app:celery_app worker \
  --loglevel=info -Q celery,document_processing \
  -c 4  2>&1 | tee -a /ManualAI/OmniKnow/logs/celery_worker.log
