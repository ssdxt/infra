#!/bin/bash
PY=/root/anaconda3/envs/recovery/bin/python
PKG=/root/anaconda3/envs/recovery/lib/python3.8/site-packages

echo "########## 1. python 与关键包版本 ##########"
$PY -V
$PY - <<'EOF'
import importlib.metadata as m
for p in ['fastapi','pydantic','pydantic-core','starlette','uvicorn','typing-extensions','anyio','gradio','langchain','langchain-core','langchain-community']:
    try: print(f"  {p:22} {m.version(p)}")
    except Exception: print(f"  {p:22} <未安装>")
EOF

echo
echo "########## 2. fastapi 安装痕迹（有没有两套）##########"
ls -d $PKG/fastapi* 2>&1
echo "--- dist-info ---"
ls -d $PKG/fastapi-*.dist-info 2>&1
echo "--- 是否存在旧的单文件 _compat.py（新版是 _compat/ 目录）---"
ls -la $PKG/fastapi/_compat.py 2>&1
ls -la $PKG/fastapi/_compat/ 2>&1

echo
echo "########## 3. _compat/__init__.py 到底写了什么 ##########"
head -40 $PKG/fastapi/_compat/__init__.py 2>&1

echo
echo "########## 4. 报错那行附近 ##########"
sed -n '15,30p' $PKG/fastapi/_compat/__init__.py 2>&1

echo
echo "########## 5. pydantic 版本决定 _compat 走哪条分支 ##########"
$PY -c "import pydantic; print('pydantic', pydantic.VERSION)" 2>&1
$PY -c "from pydantic.fields import ModelField; print('pydantic v1 ModelField OK')" 2>&1 | tail -2
$PY -c "from pydantic import TypeAdapter; print('pydantic v2 TypeAdapter OK')" 2>&1 | tail -2

echo
echo "########## 6. ErrorWrapper 在哪 ##########"
grep -rn "ErrorWrapper" $PKG/fastapi/_compat/ 2>/dev/null | head -5
$PY -c "from pydantic.error_wrappers import ErrorWrapper; print('pydantic.error_wrappers.ErrorWrapper OK')" 2>&1 | tail -2

echo
echo "########## 7. 包安装/修改时间 ##########"
stat -c '%y  %n' $PKG/fastapi/__init__.py $PKG/fastapi/_compat/__init__.py $PKG/fastapi-*.dist-info 2>&1
echo "--- 最近改动过的包（按时间倒序 top 15）---"
ls -lt --time-style=+%Y-%m-%d_%H:%M $PKG/ 2>/dev/null | grep -E "dist-info|\.egg-info" | head -15
