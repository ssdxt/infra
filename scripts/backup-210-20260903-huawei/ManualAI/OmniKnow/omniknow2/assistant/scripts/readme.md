# 启动 list resource 服务
uvicorn list_resource_service:app --host 0.0.0.0 --port 18803 --reload

# 然后在浏览器或用 curl / Postman 访问：
curl "http://127.0.0.1:18803/knowledge/list_resources"

# 启动 filt http 服务
uvicorn file_http_service:app --host 0.0.0.0 --port 18804 --reload
