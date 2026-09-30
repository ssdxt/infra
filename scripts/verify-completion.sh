#!/bin/bash
for ip in 10.100.10.10 10.100.10.14 10.100.10.19 10.100.10.33 10.100.10.34 10.100.10.39 10.100.10.41 10.100.10.44 10.100.10.45 10.100.10.46 10.100.10.47; do
  echo -n "$ip: "
  timeout 30 ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$ip \
    'bash -ic "complete -p kubectl >/dev/null 2>&1 && echo -n kubectl-OK || echo -n kubectl-NO; echo -n \" \"; complete -p k >/dev/null 2>&1 && echo -n kalias-OK || echo -n kalias-NO; echo -n \" \"; complete -p helm >/dev/null 2>&1 && echo -n helm-OK || echo -n helm-NO; echo -n \" KUBECONFIG=\${KUBECONFIG:-none}\"" 2>/dev/null' 2>/dev/null
  echo ""
done