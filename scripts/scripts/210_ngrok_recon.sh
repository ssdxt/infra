#!/bin/bash
echo '== zellij =='
which zellij 2>&1 && zellij --version 2>&1 | head -1
echo '== ngrok =='
which ngrok 2>&1 && ngrok --version 2>&1 | head -1
echo '== ngrok config on 210 =='
ls -la /root/.config/ngrok/ /root/.ngrok2/ 2>/dev/null
echo '== tmux fallback =='
which tmux 2>&1
echo '== arch =='
uname -m
echo '== ngrok download reachability =='
curl -sI --max-time 10 https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz 2>&1 | head -1
curl -sI --max-time 10 https://download.ngrok.com/linux-amd64 2>&1 | head -1
