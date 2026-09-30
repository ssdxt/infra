#!/bin/bash
cd /deploy/code/chat_doc_0918 2>/dev/null || exit 1

echo "########## 1. BASE_PORT 的值 ##########"
grep -rn "BASE_PORT" configs/*.py 2>/dev/null | head -5

echo
echo "########## 2. 参数分支逻辑（第 585-660 行）##########"
sed -n '585,660p' startup_obd.py

echo
echo "########## 3. 启动分支（第 680-730 行）##########"
sed -n '680,730p' startup_obd.py

echo
echo "########## 4. 所有 add_argument 的选项名 ##########"
sed -n '470,560p' startup_obd.py | grep -A3 "add_argument" | grep -E '"--' | head -20

echo
echo "########## 5. start_main_server 里 controller 在哪启动 ##########"
grep -n "controller\|Controller" startup_obd.py | sed -n '1,40p'
