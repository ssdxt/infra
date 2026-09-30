import asyncio
from fastmcp import Client
from schema import ParseRequest, ParseResponse,SearchRequest,SearchResponse

# client = Client("http://localhost:8008/sse")


# async def call_tool(query: str, collection_name:str, top_k:int=5):
#     async with client:
#         result = await client.call_tool("hybrid_search", 
#                                         {"query":query,
#                                         "collection_name":collection_name,
#                                         "top_k":top_k})
#         print(result)


# query = "除传统的开关和按钮外，您的车辆还配备触摸感"
# collection_name = "vehical_repair"
# top_k = 5

# asyncio.run(call_tool(query=query,
#                     collection_name=collection_name,
#                     top_k=top_k))


async def main():  
    async with Client("http://localhost:8008/sse") as client:  
        tools = await client.list_tools()  
        print("Available tools:", tools)  
        # result = await client.call_tool("add", {"a": 5, "b": 7})  
        # print("Result:", result.content[0].text)  
asyncio.run(main())




