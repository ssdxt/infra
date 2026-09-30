#!/bin/bash
echo '== depends_on 构成 =='
du -sh /ManualAI/depends_on/* 2>/dev/null | sort -h | head
ls /ManualAI/depends_on/data 2>/dev/null | head -8
echo '== Omniknow/code 构成 =='
du -sh /ManualAI/Omniknow/code/* 2>/dev/null | sort -h | head -15
echo '== MetaManual 构成 =='
ls /ManualAI/MetaManual 2>/dev/null | head -10
du -sh /ManualAI/MetaManual/* 2>/dev/null | sort -h | head -8
echo '== llm 各子目录 =='
du -sh /ManualAI/llm/* 2>/dev/null | sort -h
echo '== usr/local/bin =='
ls -la /usr/local/bin/ 2>/dev/null | grep -vE '^total' | head -15
