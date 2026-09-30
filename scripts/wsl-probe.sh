#!/bin/bash
echo "harbor="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 8 https://10.100.10.29)
echo "api10="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 8 https://10.100.10.10:6443)
echo "route:"; ip route | head -2
echo "dockerhub-auth:"$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 'https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/alpine:pull')
