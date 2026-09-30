import pandas as pd
import numpy as np
import time
from openai import OpenAI
from pymilvus import (
    connections,
    FieldSchema, CollectionSchema, DataType,
    Collection,
    Function,
    FunctionType,
    AnnSearchRequest,
    RRFRanker
)
import pickle
import requests

# =========================
# 1. 读取 parquet 数据
# =========================
df_queries = pd.read_parquet("/mnt/ddata2/cc007/omniknow2/parser/rag/embedding_dataset/queries-00000-of-00001.parquet")
df_corpus = pd.read_parquet("/mnt/ddata2/cc007/omniknow2/parser/rag/embedding_dataset/corpus-00000-of-00001.parquet")
df_dev = pd.read_parquet("/mnt/ddata2/cc007/omniknow2/parser/rag/embedding_dataset/dev-00000-of-00001.parquet")

queries_list = df_queries["text"].tolist()
queries_id_list = df_queries["id"].tolist()
corpus_list = df_corpus["text"].tolist()
corpus_list = [cor[:10240] for cor in corpus_list]
corpus_id_list = df_corpus["id"].tolist()

print(corpus_list[:6])
# =========================
# 2. 预处理 dev 数据，提高查找效率
# =========================
dev_map = {}
for _, row in df_dev.iterrows():
    qid = row["query-id"]
    cid = row["corpus-id"]
    dev_map.setdefault(qid, set()).add(cid)

# =========================
# 3. Embedding 配置0
# =========================
embedding_batch_size = 64
embedding_model = "qwen-embedding"
embedding_dimensions = 1024

rerank_base_url = "http://0.0.0.0:8022/v1/rerank"
rerank_max_len = 8192
rerank_key = "cc"
rerank_model = "qwen-rerank"

embedding_client = OpenAI(
    base_url="http://0.0.0.0:8021/v1",
    api_key="cc"
)

def build_embedding_kwargs(input_data):
    kwargs = {"model": embedding_model, "input": input_data}
    if embedding_model == "qwen-embedding":
        kwargs["dimensions"] = embedding_dimensions
        kwargs["encoding_format"] = "float"
    return kwargs


def get_vllm_rerank(query: str, texts: list):
    if len(texts) == 0:
        return np.array([]), 0

    if rerank_model == "qwen-rerank":
        prefix = '<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n'
        suffix = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
        instruction = "Given a web search query, retrieve relevant passages that answer the query"

        query_template = "{prefix}<Instruct>: {instruction}\n<Query>: {query}\n"
        document_template = "<Document>: {doc}{suffix}"

        query = query_template.format(
            prefix=prefix,
            instruction=instruction,
            query=query
        )
        texts = [
            document_template.format(doc=doc, suffix=suffix)
            for doc in texts
        ]

        rerank_max_len = 32768
    else:
        rerank_max_len = 8192

    headers = {
        "Content-Type": "application/json",
        "accept": "application/json",
        "Authorization": f"Bearer {rerank_key}",
    }

    truncated_texts = [
        truncate_text(t, rerank_max_len) for t in texts
    ]

    data = {
        "model": rerank_model,
        "query": query,
        "documents": truncated_texts,
    }

    resp = requests.post(
        rerank_base_url,
        headers=headers,
        json=data,
        timeout=3600
    )
    resp.raise_for_status()
    res = resp.json()

    result = [
        {
            "index": item["index"],
            "score": item["relevance_score"],
        }
        for item in res["results"]
    ]

    return result

def truncate_text(text: str, max_len: int = 8192) -> str:
    return text[:max_len]

def get_vllm_embedding(texts):
    """批量生成 embedding，支持单条或多条"""
    zero_vector = [0.0] * embedding_dimensions

    if isinstance(texts, str):
        texts = [texts]

    results = []
    for i in range(0, len(texts), embedding_batch_size):
        batch = texts[i:i + embedding_batch_size]
        batch = [truncate_text(t, 20480) for t in batch]
        try:
            resp = embedding_client.embeddings.create(**build_embedding_kwargs(batch))
            results.extend([r.embedding for r in resp.data])
        except Exception as e:
            # 遇到异常返回零向量
            results.extend([zero_vector] * len(batch))
            print("Embedding 失败：", e)
    return results if len(results) > 1 else results[0]

# =========================
# 4. 连接 Milvus
# =========================
connections.connect(host="localhost", port="19530")
print('连接成功')
# =========================
# 5. 定义 Collection Schema
# =========================
# fields = [
#     FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
#     FieldSchema(
#         name="text",
#         dtype=DataType.VARCHAR,
#         max_length=40960,
#         enable_analyzer=True,
#         analyzer_params={"type": "chinese"},
#         enable_match=True
#     ),
#     FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=embedding_dimensions),
#     FieldSchema(name="corpus_id", dtype=DataType.VARCHAR, max_length=128),
#     FieldSchema(name="sparse_content", dtype=DataType.SPARSE_FLOAT_VECTOR),
# ]

# schema = CollectionSchema(fields, description="demo collection")

# # BM25 Function
# bm25_function = Function(
#     name="content_bm25_emb",
#     input_field_names=["text"],
#     output_field_names=["sparse_content"],
#     function_type=FunctionType.BM25
# )
# schema.add_function(bm25_function)

collection_name = "demo2_collection"
# collection = Collection(name=collection_name, schema=schema)
collection = Collection(name=collection_name)

# =========================
# 6. 创建索引
# =========================

# dense_index_params = {
#     "index_type": "HNSW",  # IVF_FLAT也可，但HNSW更适合RAG
#     "metric_type": "COSINE",
#     "params": {"M": 16, "efConstruction": 200}
# }

# dense_index_params = {
#     "index_type": "IVF_FLAT",
#     "metric_type": "L2",
#     # "metric_type": "COSINE",
#     "index_name": "vector_index",
#     "params": {"nlist": 128},
# }

# collection.create_index("embedding", dense_index_params)

# bm_index_params = {
#     "index_type": "SPARSE_INVERTED_INDEX",
#     "metric_type": "BM25",
#     "params": {
#         "inverted_index_algo": "DAAT_MAXSCORE",
#         "bm25_k1": 1.2,
#         "bm25_b": 0.75
#     }
# }
# collection.create_index("sparse_content", bm_index_params)

# =========================
# 7. 插入数据
# =========================

# corpus_vectors = get_vllm_embedding(corpus_list)

# with open("embeddingsaaa.pkl", "wb") as f:
#     pickle.dump(corpus_vectors, f)

with open("embeddingsaaa.pkl", "rb") as f:
    corpus_vectors = pickle.load(f)

print("保存完成")
print('chunk数量：',len(corpus_vectors))
batch_size=1024

# for start in range(0, len(corpus_list), batch_size):
#     text_list = corpus_list[start : start + batch_size]
#     vector_list = corpus_vectors[start : start + batch_size]
#     id_list = corpus_id_list[start : start + batch_size]
    
#     data = [
#         text_list,
#         vector_list,
#         id_list,
#     ]
#     collection.insert(data)

# collection.flush()
collection.load()
print("Milvus 插入完成，向量加载完成")

# =========================
# 8. 查询 Hybrid Search
# =========================
# query_vectors = get_vllm_embedding(queries_list)
# with open("querysaaa.pkl", "wb") as f:
#     pickle.dump(query_vectors, f)

with open("querysaaa.pkl", "rb") as f:
    query_vectors = pickle.load(f)
    
print('query embedding finished')

top_k = 3
count = 0
total_time = 0.0

for query_id, query_vec, query_text in zip(queries_id_list, query_vectors, queries_list):
    
    start_time = time.perf_counter()
    aaa = get_vllm_embedding('年国家法定节假日为11天。根据公布的国家法定节假日调整方案，调整的主要内容包括：')

    dense_request = AnnSearchRequest(
        data=[query_vec],
        anns_field="embedding",
        # param={"metric_type": "COSINE", "params": {"ef": 16}},
        param={"metric_type": "L2", "params": {"nprobe": 16}},
        limit=top_k
    )
    sparse_request = AnnSearchRequest(
        data=[query_text],
        anns_field="sparse_content",
        param={"params": {"drop_ratio_search": 0.2}},
        limit=top_k
    )

    reranker = RRFRanker()
    results = collection.hybrid_search(
        reqs=[dense_request, sparse_request],
        rerank=reranker,
        limit=top_k,
        output_fields=["text", "corpus_id"]
    )

    # print(results)
    for hits in results[0]:
        cor_id = hits.entity.get("corpus_id")
        if cor_id in dev_map.get(query_id, set()):
            count += 1
            break
    get_vllm_rerank('年国家法定节假日为11天。根据公布的国家法定节假日调整方', ['一年国家法定节假日为11天。根据公布的国家法定节假日调整方案，调整的主要内容包括：元旦放假1天不变；春节放假3天，放假时间为农历正月初一、初二、初三；“五一”国际劳动节1天不变；“十一”国庆节放假3天；清明节、端午节、中秋节增设为国家法定节假日，各放假1天(农历节日如遇闰月，以第一个月为休假日)。3、允许周末上移下错，与法定节假日形成连休。', '【导读】根据现行我国《全国年节及纪念日放假办法》规定,全体公民放假的法定节假日总共有11天,其中包含元旦、春节等,法定节假日是根据各民族的习惯或纪念要求,统一规定用以庆祝及度假的休息时间。根据《全国年节及纪念日放假办法》规定,我国法定节假日分三种,一种是全体公民放假的节日,另一种是部分公民放假的节日及纪念日。第三种就是少数民族习惯的节日,由各少数民族聚居地区的地方人民政府,按照各该民族习惯,规定放假日期。其中全体公民放假的法定节假日总共有十一天,具体如下: 【全体公民放假的节日】 1、新年,放假1天(1月1日); 2、春节,放假3天(农历正月初一、初二、初三); 3、清明节,放假1天(农历清明当日); 4、劳动节,放假1天(5月1日); 5、端午节,放假1天(农历端午当日); 6、中秋节,放假1天(农历中秋当日); 7、国庆节,放假3天(10月1日、2日、3日)。', '答：国家规定的2016年法定节假日累计有11天。2016年法定假日一览表元旦：规定在1月1日放假1天;春节：规定在阴历除夕(十二月二十九日或三十日)至正月初二放假3天;清明节：规定在清明当日放假1天。劳动节：规定在5月1日当日放假1天。端午节：规定在端午当日放假1天。中秋节：规定在中秋当日放假1天。国庆节：规定在10月1日至3日放假3天。不过，一般在放假时国家会考虑临近的双休日一块安排休息，以2016年为例，2016年总共有5个法定节假日，共放假19天。其中，清明节(4月4日)连休3天;劳动节(5月1日)连休3天;端午节(6月9日)连休3天;中秋(9月15日)连休3天;国庆节(10月1日)连休7天。', '现在法定假日是元旦1天，春节3天，清明节1天，五一劳动节1天，端午节1天，国庆节3天，中秋节1天，共计11天。法定休息日每年52个周末总共104天。合到一起总计115天。这些日历上面都有吧，自己看呀！人生日历上面的假期很全很准，可以试一下。', '国家法定有薪假11天。根据国务院《全国年节及纪念日放假办法》规定，国家法定全体公民有薪假11天，分别是：新年，放假1天(1月1日)；春节，放假3天(农历正月初一、初二、初三)；清明节，放假1天(农历清明当日)；劳动节，放假1天(5月1日)；端午节，放假1天(农历端午当日)；中秋节，放假1天(农历中秋当日)；国庆节，放假3天(10月1日、2日、3日)。另外，3.8妇女节妇女放假半天，5.4青年节14岁以上的青年放假半天，劳动者也是带薪假日。不过，这两个带薪假日余休息日不顺延，也部另补工资。有条件的单位应实行双休日制度，因工作性质和生产特点不能实行双休日的，用人单位应当保证劳动者每周至少休息一日（连续二十四小时）。   全体公民放假的节日： 新年，放假1天（1月1日）； 春节，放假3天（农历正月初一、初二、初三）； 劳动节，放假3天（5月1日、2日、3日）； 国庆节，放假3天（10月1日、2日、3日）。  部分公民放假的节日及纪念日： 妇女节（3月8日），妇女放假半天； 青年节（5月4日），14周岁以上的青年放假半天； 建军节（8月1日），现役军人放假半天。 二七纪念日、五卅纪念日、七七抗战纪念日、九三抗战胜利纪念日、九一八纪念日、教师节、护士节、记者节、植树节等其他节日、纪念日，均不放假。 全体公民放假的假日，如果适逢星期六、日，应当在工作日补假。部分公民放假的假日，如果适逢星期六、日，则不补假。  带薪年休假 在国务院未有新规定之前，带薪年休假按广东省的以下规定执行：连续工作满一年未满五年者5天；满五年未满十年者7天；满十年未满二十年者10天；满二十年以上者14天。  婚假 职工本人结婚，可享受婚假3天。晚婚者（男年满25周岁、女年满23周岁）另增加十天。  丧假 职工的直系亲属（父母、配偶、子女）死亡，可给予3天以内丧假。职工配偶的父母死亡，经单位领导批准，可给予3天以内丧假。  生育假 女职工生育， 正常产假 90天，其中产前休假15天。因难产而剖腹、III度会阴破裂者，增加产假30天；吸引产、钳产、臀位牵引产者，增加产假15天（前两项不能相加计算）；多胞胎生育的，每多生育一个婴儿增加产假15天；实行晚育者（24周岁后生育第一胎）增加产假15天；领取《独生子女优待证》者增加产假35天，同时给假予男配偶10至15天。 流产假 （只限于领取同意生育通知书或生育证的流产假）：怀孕不满2个月的15天；不满4个月的30天；怀孕满4个月以上（含4个月）至7个月以下流产的流产假42天；满7个月以上遇死胎、死产和早产不成活的给予75天产假。 职工享受节日休假、年休假、婚假、丧假、产假期间，企业应按劳动合同的工资标准支付工资', '中国节日(中国的节日)编辑 锁定中国节,指中国民间相传的纪念日、欢庆日和被中国承认的国际通用节日等。中国法定节日 有新年[1] (1月1日,放假一天);春节(农历新年,除夕、正月初一、初二放假三天);清明节(农历清明当日,放假一天);国际劳动妇女节(3月8日,妇女放假半天);植树节(3月12日);国际劳动节(5月1日,放假一天);中国青年节(5月4日,14周岁以上的青年放假半天);端午节(农历端午当日,放假一天);国际护士节(5月12日);儿童节(6月1日,不满14周岁的少年儿童放假一天);中国共产党诞生纪念日(7月1日);中国人民解放军建军纪念日(8月1日,现役军人放假半天);教师节(9月10日);中秋节(农历中秋当日,放假一天);国庆节(10月1日,放假3天);记者节(11月8日)。'])
    end_time = time.perf_counter()
    elapsed = (end_time - start_time) * 1000
    total_time += elapsed
    print(f"查询耗时: {elapsed} ms, 当前正确匹配数: {count}")
    # break
avg_time = total_time / len(queries_list)
print(f"平均每条 query 耗时: {avg_time:.2f}ms")
print(f"Top {top_k} 准确率: {count/len(queries_list):.4f}")