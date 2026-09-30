#!/bin/bash
echo '== 尝试1: username/password =='
curl -s --max-time 10 -X POST http://localhost:8375/api/v1/auth/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin123"}' | head -c 400
echo
echo '== 尝试2: account/password =='
curl -s --max-time 10 -X POST http://localhost:8375/api/v1/auth/login -H 'Content-Type: application/json' -d '{"account":"admin","password":"admin123"}' | head -c 400
echo
