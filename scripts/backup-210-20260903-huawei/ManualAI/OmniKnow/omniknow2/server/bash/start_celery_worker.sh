#!/usr/bin/env bash
set -e

export PATH=/root/anaconda3/envs/aiserver/bin:$PATH

cd /aiserverspace

source /root/anaconda3/bin/activate aiserver

celery -A ext.celery_app:celery_app worker \
  --loglevel=info -Q celery,document_processing \
  -c 4  2>&1 | tee -a /aiserverspace/logs/celery_worker.log
