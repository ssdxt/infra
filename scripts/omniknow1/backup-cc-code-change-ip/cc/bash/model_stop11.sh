# 停止72B大模型服务 (端口9885)
kill -9 $(lsof -i:9885 -t)

# 停止Embedding服务 (端口8105)
kill -9 $(lsof -i:8105 -t)

# 停止Rerank服务 (端口8106)
kill -9 $(lsof -i:8106 -t)
