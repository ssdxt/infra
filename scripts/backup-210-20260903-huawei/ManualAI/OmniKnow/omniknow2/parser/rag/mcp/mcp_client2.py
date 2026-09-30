import asyncio
from fastmcp import Client
from schema import ParseRequest, ParseResponse,SearchRequest,SearchResponse
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from dotenv import load_dotenv
import os
load_dotenv()
BASE_URL = os.getenv("BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME")

client = MultiServerMCPClient(  
    {
        # "math": {
        #     "transport": "stdio",  # Local subprocess communication
        #     "command": "python",
        #     "args": ["/path/to/math_server.py"],
        # },
        # "weather": {
        #     "transport": "http",  # HTTP-based remote server

        #     "url": "http://localhost:8000/mcp",
        # },
        "hybrid_search": {
            "transport": "sse",
            "url": "http://localhost:8008/sse",
        },
    }
)


llm = ChatOpenAI(
    base_url=BASE_URL,
    openai_api_key=API_KEY,
    model=MODEL_NAME,
    timeout=60.0,
    max_retries=2
    )


async def main():  
    tools = await client.get_tools()
    # print(tools)
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt="You are a helpful assistant",
    )
    print(agent.invoke(
        {"messages": [{"role": "user", "content": "what is the weather in sf"}]}
    ))
    # async with Client("http://localhost:8008/sse") as client:  
    #     tools = await client.list_tools()  
    #     print("Available tools:", tools)  
        # result = await client.call_tool("add", {"a": 5, "b": 7})  
        # print("Result:", result.content[0].text)  
asyncio.run(main())




