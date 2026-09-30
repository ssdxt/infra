#!/bin/bash
set -e
export HTTPS_PROXY=http://127.0.0.1:12450
mkdir -p ~/longhorn-upgrade && cd ~/longhorn-upgrade
for v in 1.8.2 1.9.2 1.10.2 1.11.3 1.12.1 1.13.0; do
  helm pull longhorn/longhorn --version $v
done
ls -la
