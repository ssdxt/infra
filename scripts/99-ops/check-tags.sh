#!/bin/bash
for r in kyverno kyvernopre cleanup-controller readiness-checker; do
  echo -n "$r : "
  curl -sk -u admin:<HARBOR_PASSWORD> \
    "https://harbor.wuxing.local/api/v2.0/projects/kyverno/repositories/$r/artifacts" \
  | python3 -c 'import json,sys
for a in json.load(sys.stdin):
    tags=[t["name"] for t in a.get("tags") or []]
    print(a["digest"][:25], tags)'
done
