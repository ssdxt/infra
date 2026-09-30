import sys
# print(sys.path)
sys.path.append('/home/star/projects/chat_doc')
from server.knowledge_base.kb_service.faiss_kb_service import FaissKBService
from server.knowledge_base.kb_service.milvus_kb_service import MilvusKBService
from server.knowledge_base.kb_service.pg_kb_service import PGKBService
from server.knowledge_base.kb_service.es_kb_service import ESKBService
from server.knowledge_base.kb_service.zilliz_kb_service import ZillizKBService
from server.knowledge_base.migrate import create_tables
from server.knowledge_base.utils import KnowledgeFile
from server.keyword_ie import get_keywords
import os
import shutil
os.environ["CUDA_VISIBLE_DEVICES"] = "7"
kbService = FaissKBService("lb_test")
# kbService = ESKBService("test")
test_kb_name = "lb_test"
# test_file_name = "陕汽-新M3000S维修手册 第二部分.pdf"
# test_file_name = "陕汽L3000系列载货车维修手册（第二部分）.docx"
test_file_name = "陕汽-重卡X5000维修手册（第一部分）.pdf"
# test_file_name = "重型卡车维修技术手册底盘分册.pdf"
testKnowledgeFile = KnowledgeFile(test_file_name, test_kb_name)
search_content = "驱动车桥的速比数据表"


def test_init():
    create_tables()

def test_create_db(kbService):
    assert kbService.create_kb()


def test_add_doc(kbService, testKnowledgeFile):
    assert kbService.add_doc(testKnowledgeFile)


def test_search_db(kbService):
    result = kbService.search_docs(search_content)
    # result = kbService.do_search(search_content, 3, 0.5)
    # assert len(result) > 0
    return result

def test_delete_doc():
    assert kbService.delete_doc(testKnowledgeFile)


def test_update_doc():
    assert kbService.update_doc()


def test_delete_db(kbService):
    assert kbService.drop_kb()

def test_clear_emb():
    # emb_path = f"knowledge_base/{test_kb_name}/vector_store"
    # if os.path.exists(emb_path):
    #     shutil.rmtree(emb_path)
    assert kbService.clear_vs()

import json
# with open("tests/kb_vector_db/query_重卡_底盘.json", "r") as f:
#     queries = json.load(f)
queries = {
    "X5000的配的发动机型号":38,
    "WP10H系列发动机技术参数":1,
    "WP11S 系列发动机技术参数":1,
    "WP13G 系列发动机技术参数":1
}
# queries = {}
# with open("/mnt/ddata/datasets/内部数据集-训练/1.jsonl","r") as f:
#     lines = f.readlines()
#     for lineno,line in enumerate(lines):
#         line_json = json.loads(line)
#         query = line_json["conversation"][0]["human"]
#         answer = line_json["conversation"][0]["assistant"]
#         print(query,answer)
#         queries[query] =1
#         if lineno >10:
#             break

queries ={
    "WP10H系列发动机的技术规格是怎样的，它包括哪些重要的技术数据":1,
    "重型卡车发动机故障有哪些？":1
}
d = list()


# faiss的swigfaiss的indexflat.search是向量的L2距离和余弦距离
test_kb_name = "lb_test"
kbService = FaissKBService(test_kb_name)
# test_delete_db(kbService)
# test_create_db(kbService)
# test_clear_emb()
# test_add_doc(kbService, testKnowledgeFile)

# retrival_list = test_search_db(kbService)
accurate = 0

# test_delete_doc()

for query, index in queries.items(): 
    answer_list = []
    query_c = query
    # if len(keywords)>0:
    #     query_c =  ",".join(keywords)
    search_content = query_c
    answers = test_search_db(kbService)
    print(query_c,[answer[0].metadata["titles"]+"   "+answer[0].page_content  for answer in answers])
    # print(query)
    # for a in answers:
    #     print(a)

    # break
    
#     for i in range(1):
#         if answers:
#             answer_list.append([i, answers[i][0].metadata, answers[i][0].page_content[:100]])
#     if answers:
#         length = len(answers[0][0].page_content)
#         result = "1"
#         if answers[0][0].metadata['content_pos'][0]['page_no'] <= index <= answers[0][0].metadata['content_pos'][-1]['page_no']:
#             accurate += 1
#             result = "1"
#         else:
#             print()
#             print(f"问题：",query)
#             print(f"正确：{index}, 回答区间[{answers[0][0].metadata['content_pos'][0]['page_no']}, {answers[0][0].metadata['content_pos'][-1]['page_no']}]")
#             print(f"得分：{answers[0][1]}")
#             print(f"key word：{answers[0][0].metadata}")
#             print(f"答案：{repr(answers[0][0].page_content)}")
#             result = "0"
#             d.append({"page":index, 
#                 "query": query,
#                 "keywords":keywords,
#                 "answer":answer_list,
#                 "len":length})
#         # d[query]=result
# accuracy = accurate / len(queries)    
# print(f"accuracy: {accuracy}")          
# with open("tests/kb_vector_db/answer_重卡_底盘_base_simple.json", "w", encoding='utf-8') as f:
#     json.dump(d, f, ensure_ascii=False, indent=4)
# retrival_list[i][1]是相似度分数, retrival_list[i][0].page_content是文本, retrival_list[i][0].metadata['source']是source

print("=============================================================================================")

# test_kb_name = "test1"
# kbService = ESKBService(test_kb_name)
# test_create_db(kbService)
# test_add_doc(kbService, testKnowledgeFile)
# print(test_search_db(kbService))
# print("=============================================================================================")
# from server.db.base import Base, engine
# Base.metadata.create_all(bind=engine)
# test_kb_name = "test2"
# kbService = ZillizKBService(test_kb_name)
# test_create_db(kbService)
# test_add_doc(kbService, testKnowledgeFile)
# print(test_search_db(kbService))
# print("=============================================================================================")

# test_kb_name = "test3"
# kbService = PGKBService(test_kb_name)
# test_create_db(kbService)
# test_add_doc(kbService, testKnowledgeFile)
# print(test_search_db(kbService)) # 针对PostgreSQL
# print("=============================================================================================")

# test_kb_name = "test4"
# kbService = MilvusKBService(test_kb_name)
# test_create_db(kbService)
# test_add_doc(kbService, testKnowledgeFile)
# print(test_search_db(kbService)) # 大规模数据库，扩展性强
# print("=============================================================================================")


if __name__ == "__main__":
    
    pass