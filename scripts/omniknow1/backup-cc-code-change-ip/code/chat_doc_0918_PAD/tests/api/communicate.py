# import time
# import requests
# import json
# import sseclient
# from const import *
# import random
# import os
# import re

# def get_random_seed():
#     current_time = int(time.mktime(time.gmtime()))
#     random.seed(current_time)
#     rand = random.randint(0, 65536)
#     return rand

# def get_new_task_id(): # 新建对话
#     url = NEW_CHAT_URL
#     payload = json.dumps({
#         "prompt": INSTRUCTION,
#         "institution": ""
#     })
#     headers = {
#             'Authorization': AUTHORIZATION,
#             'Content-Type': 'application/json;charset=UTF-8'
#         }
#     response = requests.request("POST", url, headers=headers, data=payload)
#     response_json = json.loads(response.text)
#     print(response_json)
#     return response_json['result']['task_id']

# def request_gen(prompt, conversation_task_id): # 对话请求
#     url = STREAM_CHAT_URL
#     payload = json.dumps({
#         "conversation_task_id": conversation_task_id,
#         "img_list": [],
#         "institution": "",
#         # "max_tokens": 512,
#         "optimization_id": "",
#         "prompt": prompt,
#         "seed": get_random_seed(),
#         "request_type": "general_4_image",
#         "retry": False,
#         "retry_history_task_id": None,
#         "seed": 35298,
#         "tm": "pc",
#         "__userid": "64bfcd809fc4fa8f60df9903"
#     })
#     headers = {
#         'Authorization': AUTHORIZATION,
#         'Cookie': COOKIE,
#         'Content-Type': 'application/json'
#     }
#     response = requests.request("POST", url, headers=headers, data=payload)
#     response_json = json.loads(response.text)
#     return response_json["result"]["context_id"]


# def get_generate_result(context_id): # 获取answer
#     import sseclient
#     url = "https://chatglm.cn/chatglm/backend-api/v1/stream?App-Name=chatglm&context_id={}&institution=".format(context_id)
#     # url = "https://chatglm.cn/chatglm/backend-api/v1/stream_context?__requestid={}".format(context_id)
#     # payload = {}
#     headers = {
#         'Cookie': COOKIE
#     }
#     print("url",url)
#     response = requests.request("GET", url)
#     print("response",response)
#     client = sseclient.SSEClient(response)
#     str = ""
#     for event in client.events():
#         if event.data != '[DONE]':
#             str = event.data
#         else:
#             pass
#     return str
# def chat(prompt, conversation_task_id):
#     t1 = time.time()*1000
#     context_id = request_gen(prompt, conversation_task_id)
#     print("context_id",context_id)
#     result = get_generate_result(context_id=context_id)
#     print(time.time()*1000-t1)
#     return result

# if __name__ == "__main__":
#     # file_path = "111.json"
#     # in_path = "in4.json"
#     # if not os.path.isfile(in_path):
#     #     with open(in_path, 'w') as f:
#     #         json.dump([], f)
#     # with open(file_path, 'r') as f:
#     #     data = json.load(f)
#     # context_list = []
#     # for content in data:
#     #     if len(content[2]) > 50:
#     #         context_list.append(content[1]['titles']+content[2])
#     # max_retries = 3
#     # retry_delay = 10
#     # conversation_task_id = get_new_task_id()
#     # first_answer = chat(INSTRUCTION, conversation_task_id)
#     # time.sleep(10)
#     # for index, context in enumerate(context_list):
#     #     # if index < 517:
#     #     #     continue
#     #     for attempt in range(1, max_retries + 1):
#     #         try:
#     #             print(f"{index}")
#     #             answer = chat(context+PROMPT, conversation_task_id)
#     #             answer = re.sub(r'\s+', '', answer)
#     #             answer = answer.replace('"，', '", ').replace('}，', '}, ')
#     #             if answer[:3] != '[{"':
#     #                 first_occurrence_position = answer.find('{"')
#     #                 answer = '[' + answer[first_occurrence_position:]
#     #             if answer[-3:] != '"}]':
#     #                 last_occurrence_position = answer.rfind('},')
#     #                 answer = answer[:last_occurrence_position+1]+']'
#     #             print(answer)
#     #             answer = json.loads(answer)

#     #             with open(in_path, 'r') as json_file:
#     #                 previous_answers = json.load(json_file)

#     #             previous_answers.extend(answer)
#     #             with open(in_path, 'w') as f:
#     #                 json.dump(previous_answers, f, ensure_ascii=False, indent=4)
#     #             time.sleep(10)
#     #             # if index % 20 == 0 and index != 0:
#     #             #     conversation_task_id = get_new_task_id()
#     #             #     first_answer = chat(INSTRUCTION, conversation_task_id)
#     #             #     time.sleep(10)

#     #         except Exception as e:
#     #             print(f"Attempt {attempt}: Exception - {e}")
                
#     #             if attempt < max_retries:
#     #                 print(f"Retrying in {retry_delay} seconds...")
#     #                 time.sleep(retry_delay)
#     #                 continue  # Go back to the beginning of the loop for another attempt
#     #             else:
#     #                 print("Max retry attempts reached. Exiting.")
#     #                 conversation_task_id = get_new_task_id()
#     #                 first_answer = chat(INSTRUCTION, conversation_task_id)
#     #                 print(f"new conversation id: {conversation_task_id}")
#     #                 time.sleep(10)
#     #         # If no exception occurred or max_retries reached, break out of the loop
#     #         break
    
    
    
#     conversation_task_id = get_new_task_id()
#     # print("conversation_task_id",conversation_task_id)
#     # context = "[['', '', '上下刻度线之间'], ['冷却液容积（L）', '', '15'], ['怠速机油压力（kPa）', '', '100-320'], ['曲轴旋转方向（从发动机前方看）', '', '顺时针'], ['负载工作机油压力（kPa）', '', '370-580'], ['进气阻力（kPa）', '', '<3.5(干净滤芯)/<7(滤芯储尘后)'], ['最大允许排气背压（kPa）', '', '18'], ['燃油滤清器', '最大流量（L/h）', '460'], ['', '初始阻力（kPa）', '≤8'], ['', '接口尺寸', 'M16×1.5'], ['清洁度限值(mg)', '', '1710']]"
#     # query = "WP10H系列发动机的技术规格是怎样的，它包括哪些重要的技术数据"
    
#     q = """你是一个汽车维修专家，请结合下面的 '已知信息' 回答问题。直接输出答案即可，不用附带任何上下文。答案简洁、合理，避免重复;字数控制在 '100' 字以内。\n已知信息：'{}'\n问题：'{}'\n 回答：""".format(context,query)
#     first_answer = chat(q, conversation_task_id)
#     print("first_answer",first_answer)