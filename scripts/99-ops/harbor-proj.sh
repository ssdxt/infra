#!/bin/bash
export NO_PROXY=harbor.wuxing.local,10.100.10.29
export no_proxy=harbor.wuxing.local,10.100.10.29
unset HTTPS_PROXY https_proxy
HARBOR=harbor.wuxing.local
echo "--- ping ---"
curl -sk -o /dev/null -w 'ping:%{http_code}\n' https://$HARBOR/api/v2.0/ping
echo "--- create project ---"
curl -sk -u 'admin:<HARBOR_PASSWORD>' -X POST https://$HARBOR/api/v2.0/projects \
  -H 'Content-Type: application/json' \
  -d '{"project_name":"kyverno","public":false}' \
  -o /tmp/cr.out -w 'create:%{http_code}\n'
cat /tmp/cr.out; echo
echo "--- list projects ---"
curl -sk -u 'admin:<HARBOR_PASSWORD>' https://$HARBOR/api/v2.0/projects -o /tmp/p.json -w 'list:%{http_code}\n'
grep -o '"name":"[a-z0-9_-]*"' /tmp/p.json
