# https_server.py
import http.server
import ssl

# 设置服务器地址和端口
server_address = ('0.0.0.0', 3333)  # 注意：默认不能使用 443 端口（需要 root）

# 使用简单的HTTP处理器
httpd = http.server.HTTPServer(server_address, http.server.SimpleHTTPRequestHandler)

# 使用自签名证书（自行生成）
httpd.socket = ssl.wrap_socket(httpd.socket,
                               keyfile="./key.pem",
                               certfile="./cert.pem",
                               server_side=True)

print("Serving on https://0.0.0.0:3333")
httpd.serve_forever()
