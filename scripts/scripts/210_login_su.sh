#!/bin/bash
echo '== su/admin123 =='
curl -s --max-time 10 -X POST http://localhost:8375/api/v1/auth/login -H 'Content-Type: application/json' -d '{"username":"su","password":"admin123"}' | head -c 500
echo
