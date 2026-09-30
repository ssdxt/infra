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
import json

os.environ["CUDA_VISIBLE_DEVICES"] = "7"


# test_file_name = "陕汽-重卡X5000维修手册（第一部分）.pdf"
# testKnowledgeFile = KnowledgeFile(test_file_name, test_kb_name)
# search_content = ""


def test_init():
    create_tables()

def test_create_db(kbService):
    assert kbService.create_kb()


def test_add_doc(kbService, testKnowledgeFile):
    result =  kbService.add_doc(testKnowledgeFile)
    print(result)
    assert result


def test_search_db(kbService,query,topk=3,score=0.5):
    # result = kbService.search_docs(query)
    print("topk:",topk)
    result = kbService.do_search(query,topk,score)
    # assert len(result) > 0
    return result

def test_delete_doc(testKnowledgeFile):
    assert kbService.delete_doc(testKnowledgeFile)


def test_update_doc():
    assert kbService.update_doc()


def test_delete_db(kbService):
    assert kbService.drop_kb()

def test_clear_emb():
    assert kbService.clear_vs()


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


accurate = 0

# test_delete_doc()

# for query, index in queries.items(): 
#     answer_list = []
#     query_c = query
#     # if len(keywords)>0:
#     #     query_c =  ",".join(keywords)
#     search_content = query_c
#     answers = test_search_db(kbService)
#     print(query_c,[answer[0].metadata["titles"]+"   "+answer[0].page_content  for answer in answers])
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



if __name__ == "__main__":
    # test_kb_name = "test_emb"
    # kbService = FaissKBService(test_kb_name)
    # test_create_db(kbService)
    # test_clear_emb()
    
    # test_file_name ="一学就会的500项汽车维修技能_第2版.pdf"
    # test_file_name ="一学就会的500项汽车维修技能_第2版_emb.pdf"
    # test_file_name ="最新汽车维修1128问_emb.pdf"
    # test_file_name ="汽车典型故障快修200例（全彩版）_emb.pdf"
    
    
    knowledge_base_name = "test_nuclear"
    kbService = FaissKBService(knowledge_base_name)
    # 
    # test_file_name ="非能动安全先进核电厂AP1000.pdf"
    # test_file_name = "中国自主先进压水堆技术“华龙一号”(下册).pdf"
    
    knowledge_filenames = ["中国自主先进压水堆技术“华龙一号”(下册).pdf","中国自主先进压水堆技术“华龙一号”(上册).pdf","非能动安全先进核电厂AP1000.pdf"]
    # knowledge_filenames=[]
    #获取当前项目库路径
    import glob
    pdf_dir ="knowledge_base/"+knowledge_base_name+"/content/"
    for filename in glob.glob(pdf_dir+"*.pdf"):
        knowledge_filenames.append(os.path.basename(filename))
    print("knowledge_filenames",knowledge_filenames)
    
    # q = "核电厂整体描述"
    # retrival_list = test_search_db(kbService,q,1,1)
    # print("retrival_list",retrival_list)

    
    image_title_list = ["图1.1 AP1000 核岛反应堆冷却剂系统的布置图","图1.2 AP1000 安全壳布置图","图1.3 AP1000 场址布置图"]
    # image_query_list= ["能帮我找一张AP1000核岛反应堆冷却剂系统的布置图吗？","可以帮我搜寻一张AP1000核岛反应堆冷却剂系统的布局图吗？","能否协助我获取一张AP1000核岛反应堆的冷却剂系统配置图？","我需要一张AP1000核岛反应堆冷却剂系统的布局图，你能帮我找到吗？"]
    image_query_list= ["能帮我找一张AP1000核岛反应堆冷却剂系统的布置图？"]
    
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('/mnt/ddata/models/bge-large-zh-v1.5.4')
    
    for image_query in image_query_list:
        q_embeddings = model.encode([image_query], normalize_embeddings=True)
        p_embeddings = model.encode(image_title_list, normalize_embeddings=True)
        scores = q_embeddings @ p_embeddings.T
        print(image_query,scores[0]>0.80)
    
    # from sentence_transformers import SentenceTransformer
    # sentences_1 = ["样例数据-1", "样例数据-2"]
    # sentences_2 = ["样例数据-3", "样例数据-4"]
    # model = SentenceTransformer('/mnt/ddata/models/bge-large-zh-v1.5.4')
    # embeddings_1 = model.encode(sentences_1, normalize_embeddings=True)
    # embeddings_2 = model.encode(sentences_2, normalize_embeddings=True)
    # similarity = embeddings_1 @ embeddings_2.T
    # print(similarity)
    
    
    

    
    def read_querys():
        test_clear_emb()
        import csv
        for file_name in knowledge_filenames:
            print(file_name)
            testKnowledgeFile = KnowledgeFile(file_name.replace("_emb",""), knowledge_base_name)
            test_add_doc(kbService, testKnowledgeFile)
            
            with open("knowledge_base/"+knowledge_base_name+"/csv/"+file_name.replace(".pdf","copy.csv"), 'r') as csvfile:
                queries = []
                reader = csv.reader(csvfile)
                for row in reader:
                    query,context= row[0],row[1]
                    query =query[str(query).rfind("#")+1:].strip()
                    if len(query)>5:
                        query_list = [query]
                        if len(row)>2:
                            human_querys = row[2].split("\n")
                            if len(human_querys)>0:
                                query_list.extend(human_querys)
                        query_list.append(context)
                        queries.append(query_list)
        


    # queries = read_querys()
                
def acc(queries,kbService):
    success_count=0
    query_count=0
    avg_score =0
    for query_list in queries[0:]:
        query = query_list[0]
        for q in query_list[:-1]:
            if len(q.strip())==0:
                continue
            query_count+=1
            retrival_list = test_search_db(kbService,q,1,0.65)
            retrival_result = False
            for retrival in retrival_list:
                document,score = retrival[0],retrival[1]
                titles = document.metadata["titles"]
                images = " ".join(document.metadata["images"])
                if (str(titles).find(query)>-1 or str(images).find(query)>-1):
                    retrival_result =True
                    avg_score+=score
                    break
    
            if retrival_result:
                success_count+=1
            else:
                print(q,query,retrival_list)
                print("------------------")
                pass
 
    print("成功率:",success_count,query_count,float(success_count/query_count))

# acc(queries,kbService)
    
    # 一学就会的500项汽车维修技能_第2版.pdf
    # 1,0.65 
    # 成功率: 0.8734439834024896
    # 2,0.65
    # 成功率: 0.9543568464730291
    
    # bge-large-zh-v1.5默认模型，使用人类自己问题时，
  
    # 1,0.65 情况下效果成功率: 91 129 0.627906976744186   72 95 0.7578947368421053
    # 2,0.65 情况下效果成功率: 91 129 0.7054263565891473  成功率: 74 95 0.7789473684210526
    # 2,0.65 情况下效果成功率: 91 129 0.7054263565891473  成功率: 74 95 0.7789473684210526
    
    # 成功率: 93 95 0.9789473684210527
    
    # retrival_list = test_search_db(kbService,"怎么选配曲轴主轴承",5,1)
    # print("retrival_list:",retrival_list)
    
    
    # 核电 v1.5版本，0-100： 122 235 0.5191489361702127
    # 核电 v1.5版本，0-： 122 235 0.5191489361702127
    # 核电 v1.5.3版本，100- 313 379 0.8258575197889182
    # 核电 v1.5.3版本，0- 404 614 0.6579804560260586
    # 核电 v1.5.3版本，: 515 614 0.8387622149837134
    # 核电 v1.5.2版本，:  898 2095 0.4286396181384248 三本书

    
def build_emb_finetune_jsonl_file(queries,kbService):
    emb_pre=[]
    #保留前60个作为测试集
    for query_list in queries[:300]:
        context =query_list[-1]
        query_list =query_list[:-1]
        query = query_list[0]
       
        for q in query_list[:]:
            if len(q.strip())==0:
                continue
            pos =[]
            neg =[]
            retrival_list = test_search_db(kbService,q,5,2)
            retrival_result = False
            for retrival in retrival_list[:5]:
                document,score = retrival[0],retrival[1]
                titles = document.metadata["titles"]
                images = " ".join(document.metadata["images"])
                if (str(titles).find(query)>-1 or str(images).find(query)>-1):
                    retrival_result =True
                    pos.append(document.page_content)
                else:
                    neg.append(document.page_content)
            if retrival_result:
                pass
            else:

                pass
            
            if len(pos) == 0:
                pos.append(context)
            if len(neg) <5:
                import random
                for i in range(5-len(neg)):
                    selected = queries[random.randint(0,len(queries)-1)]
                    selected_context = selected[-1]
                    if selected_context != context:
                        neg.append(selected_context)
                pass
            
            emb_pre.append({"query":q,"pos":pos,"neg":neg})
    finetune_emb_filename = '../FlagEmbedding/FlagEmbedding/baai_general_embedding/finetune/'+knowledge_base_name+'.jsonl'
    with open(finetune_emb_filename, 'w') as jsonl_file:
        for entry in emb_pre:
            json.dump(entry, jsonl_file,ensure_ascii=False)
            jsonl_file.write('\n')
            
# build_emb_finetune_jsonl_file(queries,kbService)






