import requests
import json

# 接口地址
url = "http://192.168.5.163:8106"

# 请求体

data = [
    {"index": 1, "score": 0.6077796},
    {"index": 0, "score": 0.5076746},
    {"index": 2, "score": 0.09704755}
]

# 方法1：使用 sorted（返回新列表）
sorted_data = sorted(data, key=lambda x: x["index"])
print(sorted_data)

# 方法2：使用 list.sort（直接修改原列表）
data.sort(key=lambda x: x["index"])
print(data)
#
