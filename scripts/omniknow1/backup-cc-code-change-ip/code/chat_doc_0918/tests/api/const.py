INSTRUCTION = "接下来我会给你一段内容，在内容后会跟随一段指令，请严格按照指令执行。"
PROMPT = """\n接下来是指令
1. 你是一个装备维修方面专家，你需要确保你的回答是正确的。
2. 你的任务是根据我给出的内容，生成适合作为大模型微调的问答对数据集，你需要把这次对话的内容与前面对话的内容结合起来理解。
3. 内容格式参考pdf格式，忽略和图片有关的信息。
4. Question为情景加问题，情景部分需要描述问题所在的场景以及条件。答案要全面，多使用我的信息，内容要更丰富。
5. 情景要详细准确且全面有辨识度，答案需要和情景和问题强相关。
6. 输出格式为python格式，最外层为一个python list，在list里面每个问答对为一个python dict。
7. 以下生成问答对示例，你必须根据严格遵守问答对示例格式：
[{"Question": "车子是德龙 M3000 车型，电源部分主要包括哪些", "Answer": "德龙 M3000 车型的电源部分主要包括蓄电池 G100、G101，电源总开关 S4，发电机 G102，以及两路保险丝盒 F604、F605。"},
{"Question": "对于富勒变速箱，富勒变速箱常见的故障有哪些", "Answer": "1换档困难\n一般对刚接触装有富勒变速箱的汽车时，常反映该车起步不好挂档。2变速箱脱(掉)档\n汽车在运行中某一档位经常掉档，特别是在急加速(突然施加负荷)或突然减\n速(丢油门)时较为明显。"}]
8. 用于分割Question和Answer的逗号需要用英文逗号字符表示。"""
PROMPT2 = """\n你只需要按照最初规定的python格式返回a list of dicts，格式严格遵守[{"Question": "问题1", "Answer": "答案1"},
{"Question": "问题2", "Answer": "答案2"}]"""
# AUTHORIZATION = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTcwMjYyMDgyMCwianRpIjoiOWU1OGU2NTUtMjRlMi00YmVhLTlhZmItNGM4ODZmZjUzMmI2IiwidHlwZSI6ImFjY2VzcyIsInN1YiI6ImQ2MzQ4YTc0ZTg2ZjQwZDU4MTQyMWJjMDM0YTFiNTBkIiwibmJmIjoxNzAyNjIwODIwLCJleHAiOjE3MDI3MDcyMjAsInVpZCI6IjY1NDFhZTZhMDgzYzk1YTAzYTMxOGU2NCIsInVwbGF0Zm9ybSI6InBjIiwicm9sZXMiOlsidW5hdXRoZWRfdXNlciJdfQ.W72S0FVcdUCLFTIEJ8YPcuhtbYEfzI5dpm1G-W2-3nk"
# AUTHORIZATION2 = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTY5ODgwMzMwOCwianRpIjoiM2QxOTkzZDYtMjEyZi00ZjJhLWI0NTQtY2I1M2JlMTk0OTFjIiwidHlwZSI6ImFjY2VzcyIsInN1YiI6ImQ2MzQ4YTc0ZTg2ZjQwZDU4MTQyMWJjMDM0YTFiNTBkIiwibmJmIjoxNjk4ODAzMzA4LCJleHAiOjE2OTg4ODk3MDgsInJvbGVzIjpbInVuYXV0aGVkX3VzZXIiXX0.hG4tebiclWXAWApVFlDhBmbz_Ui5m9bokfQ-eWyIqW4"
# COOKIE = "sensorsdata2015jssdkchannel=%7B%22prop%22%3A%7B%22_sa_channel_landing_url%22%3A%22%22%7D%7D; _ga=GA1.1.2014748101.1698803281; sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%226541ae6a083c95a03a318e64%22%2C%22first_id%22%3A%2218b8890e98b620-0684e196ca697d8-26031151-2073600-18b8890e98c1cf6%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E8%87%AA%E7%84%B6%E6%90%9C%E7%B4%A2%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC%22%2C%22%24latest_referrer%22%3A%22https%3A%2F%2Fwww.google.com%2F%22%2C%22_latest_wx_ad_click_id%22%3A%22%22%2C%22_latest_wx_ad_hash_key%22%3A%22%22%2C%22_latest_wx_ad_callbacks%22%3A%22%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMThiODg5MGU5OGI2MjAtMDY4NGUxOTZjYTY5N2Q4LTI2MDMxMTUxLTIwNzM2MDAtMThiODg5MGU5OGMxY2Y2IiwiJGlkZW50aXR5X2xvZ2luX2lkIjoiNjU0MWFlNmEwODNjOTVhMDNhMzE4ZTY0In0%3D%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%24identity_login_id%22%2C%22value%22%3A%226541ae6a083c95a03a318e64%22%7D%2C%22%24device_id%22%3A%2218b8890e98b620-0684e196ca697d8-26031151-2073600-18b8890e98c1cf6%22%7D; acw_tc=7ae4df1a17026207891481915ea960949c7c62d172e353f93fa5ccb9d9; cdn_sec_tc=7ae4df1a17026207891481915ea960949c7c62d172e353f93fa5ccb9d9; chatglm_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTcwMjYyMDgyMCwianRpIjoiOWU1OGU2NTUtMjRlMi00YmVhLTlhZmItNGM4ODZmZjUzMmI2IiwidHlwZSI6ImFjY2VzcyIsInN1YiI6ImQ2MzQ4YTc0ZTg2ZjQwZDU4MTQyMWJjMDM0YTFiNTBkIiwibmJmIjoxNzAyNjIwODIwLCJleHAiOjE3MDI3MDcyMjAsInVpZCI6IjY1NDFhZTZhMDgzYzk1YTAzYTMxOGU2NCIsInVwbGF0Zm9ybSI6InBjIiwicm9sZXMiOlsidW5hdXRoZWRfdXNlciJdfQ.W72S0FVcdUCLFTIEJ8YPcuhtbYEfzI5dpm1G-W2-3nk; chatglm_token_expires=2023-12-15%2016:13:42; chatglm_refresh_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTcwMjYyMDgyMCwianRpIjoiOTMxNTAzOWEtYzcxNi00Mzk3LWIzMzYtYWVmYmFhYWY5NzliIiwidHlwZSI6InJlZnJlc2giLCJzdWIiOiJkNjM0OGE3NGU4NmY0MGQ1ODE0MjFiYzAzNGExYjUwZCIsIm5iZiI6MTcwMjYyMDgyMCwiZXhwIjoxNzE4MTcyODIwLCJ1aWQiOiI2NTQxYWU2YTA4M2M5NWEwM2EzMThlNjQiLCJ1cGxhdGZvcm0iOiJwYyIsInJvbGVzIjpbInVuYXV0aGVkX3VzZXIiXX0.axR0b7BAhc1v3HXyl1M6iBkOWJfYx2idtcUSLjq0ve0; chatglm_user_id=6541ae6a083c95a03a318e64; abtestid=b; _ga_PMD05MS2V9=GS1.1.1702620791.24.1.1702620954.0.0.0"
# REQUEST_ID = {
#   "intFields": [
#     3417222477,
#     28843,
#     16821,
#     179,
#     65,
#     114352290883442
#   ],
#   "bitFields": [
#     "11001011101011101010110101001101",
#     "0111000010101011",
#     "0100000110110101",
#     "10110011",
#     "01000001",
#     "011010000000000010110111101011010110011101110010"
#   ],
#   "hexFields": [
#     "cbaead4d",
#     "70ab",
#     "41b5",
#     "b3",
#     "41",
#     "6800b7ad6772"
#   ],
#   "version": 4,
#   "bitString": "11001011101011101010110101001101011100001010101101000001101101011011001101000001011010000000000010110111101011010110011101110010",
#   "hexNoDelim": "cbaead4d70ab41b5b3416800b7ad6772",
#   "hexString": "cbaead4d-70ab-41b5-b341-6800b7ad6772",
#   "urn": "urn:uuid:cbaead4d-70ab-41b5-b341-6800b7ad6772"
# }

AUTHORIZATION = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTcwNTM5MTQ4MSwianRpIjoiMDY5MGNmNmUtZjcyMS00N2I4LWExOTItMTA3ZjQ0ZjU3ZWNlIiwidHlwZSI6ImFjY2VzcyIsInN1YiI6IjkwM2RiNWIwMGU2MjRiY2M4MTA5ZmVhZmVlZWFmNTA2IiwibmJmIjoxNzA1MzkxNDgxLCJleHAiOjE3MDU0Nzc4ODEsInVpZCI6IjY0YmZjZDgwOWZjNGZhOGY2MGRmOTkwMyIsInVwbGF0Zm9ybSI6IiIsInJvbGVzIjpbInVuYXV0aGVkX3VzZXIiXX0.idMJiWf8GbtuRrgvoUinpym9xBUFr1quWy_cy6VQppQ"
COOKIE = "sensorsdata2015jssdkchannel=%7B%22prop%22%3A%7B%22_sa_channel_landing_url%22%3A%22%22%7D%7D; _ga=GA1.1.1118890931.1697183978; sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%2264bfcd809fc4fa8f60df9903%22%2C%22first_id%22%3A%2218b280c50d97d4-0b52622f9e3c428-18525634-1764000-18b280c50daf10%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E7%9B%B4%E6%8E%A5%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC_%E7%9B%B4%E6%8E%A5%E6%89%93%E5%BC%80%22%2C%22%24latest_referrer%22%3A%22%22%2C%22_latest_wx_ad_click_id%22%3A%22%22%2C%22_latest_wx_ad_hash_key%22%3A%22%22%2C%22_latest_wx_ad_callbacks%22%3A%22%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMThiMjgwYzUwZDk3ZDQtMGI1MjYyMmY5ZTNjNDI4LTE4NTI1NjM0LTE3NjQwMDAtMThiMjgwYzUwZGFmMTAiLCIkaWRlbnRpdHlfbG9naW5faWQiOiI2NGJmY2Q4MDlmYzRmYThmNjBkZjk5MDMifQ%3D%3D%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%24identity_login_id%22%2C%22value%22%3A%2264bfcd809fc4fa8f60df9903%22%7D%2C%22%24device_id%22%3A%2218b280c50d97d4-0b52622f9e3c428-18525634-1764000-18b280c50daf10%22%7D; chatglm_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTcwNTM5MTQ4MSwianRpIjoiMDY5MGNmNmUtZjcyMS00N2I4LWExOTItMTA3ZjQ0ZjU3ZWNlIiwidHlwZSI6ImFjY2VzcyIsInN1YiI6IjkwM2RiNWIwMGU2MjRiY2M4MTA5ZmVhZmVlZWFmNTA2IiwibmJmIjoxNzA1MzkxNDgxLCJleHAiOjE3MDU0Nzc4ODEsInVpZCI6IjY0YmZjZDgwOWZjNGZhOGY2MGRmOTkwMyIsInVwbGF0Zm9ybSI6IiIsInJvbGVzIjpbInVuYXV0aGVkX3VzZXIiXX0.idMJiWf8GbtuRrgvoUinpym9xBUFr1quWy_cy6VQppQ; chatglm_token_expires=2024-01-16%2017:51:22; chatglm_refresh_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTcwNTM5MTQ4MSwianRpIjoiNTMxYWQxNjgtOWExZi00NTY0LTk4ZGQtODUwMGJkYWM5ODhlIiwidHlwZSI6InJlZnJlc2giLCJzdWIiOiI5MDNkYjViMDBlNjI0YmNjODEwOWZlYWZlZWVhZjUwNiIsIm5iZiI6MTcwNTM5MTQ4MSwiZXhwIjoxNzIwOTQzNDgxLCJ1aWQiOiI2NGJmY2Q4MDlmYzRmYThmNjBkZjk5MDMiLCJ1cGxhdGZvcm0iOiIiLCJyb2xlcyI6WyJ1bmF1dGhlZF91c2VyIl19.I8VqTf01NXDzWaMaIF84k8sKkHRY8lWYI0tHTmBNPRw; chatglm_user_id=64bfcd809fc4fa8f60df9903; acw_tc=3adc341917054540603976104e6e8c9429126c35d4b9b67e61970dc33d; cdn_sec_tc=3adc341917054540603976104e6e8c9429126c35d4b9b67e61970dc33d; _ga_PMD05MS2V9=GS1.1.1705454076.25.0.1705454076.0.0.0; abtestid=a"

STREAM_CHAT_URL = "https://chatglm.cn/chatglm/backend-api/v1/stream_context"
NEW_CHAT_URL = "https://chatglm.cn/chatglm/backend-api/v1/conversation"
