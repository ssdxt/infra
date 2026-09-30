#!/bin/bash
for ip in 10.100.10.10 10.100.10.14 10.100.10.19 10.100.10.33 10.100.10.34 10.100.10.39 10.100.10.41 10.100.10.44 10.100.10.45 10.100.10.46 10.100.10.47; do
  echo "@@@@@@@@@@ $ip"
  scp -q -o BatchMode=yes -o StrictHostKeyChecking=no /tmp/setup-completion.sh root@$ip:/tmp/ 2>/dev/null
  timeout 180 ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$ip 'bash /tmp/setup-completion.sh 2>&1 | tail -20' 2>/dev/null
done