from pymilvus import connections, utility, Collection

connections.connect("default", host="localhost", port="19530")

# 列出所有 collections
colls = utility.list_collections()
print("Collections:", colls)

# # 查看每个 collection 的统计信息
# for name in colls:
#     try:
#         c = Collection(name)
#         print("-" * 40)
#         print("Collection:", name)
#         print("Schema:", c.schema)
#         print("Indexes:", c.indexes)
#         print("Entity count:", c.num_entities)
#     except Exception as e:
#         print("Error loading collection:", name, e)

from langchain_openai import OpenAIEmbeddings
from langchain_milvus.vectorstores import Milvus as LangchainMilvus

embeddings = OpenAIEmbeddings(
    openai_api_base="http://0.0.0.0:8115/v1",
    openai_api_key="cc",
    model="embed",
)

client = LangchainMilvus(
                    embedding_function=embeddings,
                    collection_name='ap1000',
                    # collection_name='examples',
                    connection_args={
                        "uri": "http://localhost:19530",
                    },
                    # optional (if collection already exists with different schema, be careful)
                    drop_old=False,
                )
resp = client.similarity_search(
                    query="汽车汽缸维护",
                    k=10,
                    expr='source in ["mineru"] and type in ["text"]'
                )
print(resp)

resp = client.similarity_search(
                    query="杭州",
                    k=10,
                    expr='source in ["websites"]'
                )
print(resp)

resp = client.similarity_search(
                    query="杭州",
                    k=10,
                    expr='source in ["examples"]'
                )
print(resp)