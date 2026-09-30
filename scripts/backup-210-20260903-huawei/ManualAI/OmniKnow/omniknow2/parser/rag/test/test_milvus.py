from pymilvus import MilvusClient, DataType

client = MilvusClient(
    uri="http://0.0.0.0:19530",
    # token="root:Milvus"
)

res = client.list_collections()
# print(res)

res = client.describe_collection(
    collection_name="tesla_manual"
)

print(res)

# print(client.num_entities("your_collection_name"))
# from pymilvus import Collection

# collection = Collection("your_collection_name")
# print(collection.num_entities)

