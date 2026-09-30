#!/usr/bin/env bash
set -e

export PATH=/root/anaconda3/envs/aiserver/bin:$PATH

cd /aiserverspace

source /root/anaconda3/bin/activate aiserver


python /aiserverspace/main.py 2>&1 | tee -a /aiserverspace/logs/aiserver.log
