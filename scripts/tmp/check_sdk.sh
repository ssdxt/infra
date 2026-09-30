#!/bin/bash
docker exec ai_server python3 -c "import minio; print('minio', minio.__version__)" 2>&1 | tail -1
docker exec ai_server python3 -c "import boto3; print('boto3', boto3.__version__)" 2>&1 | tail -1
docker exec ai_server python3 -c "import sys; print(sys.version.split()[0])"
