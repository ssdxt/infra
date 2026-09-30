#!/bin/bash
echo '== su + base64(admin123) 登录 =='
RESP=$(curl -s --max-time 10 -X POST http://localhost:8375/api/v1/auth/login -H 'Content-Type: application/json' -d '{"username":"su","password":"YWRtaW4xMjM="}')
echo "$RESP" | head -c 600
echo
