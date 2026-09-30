import os


# 可以指定一个绝对路径，统一存放所有的Embedding和LLM模型。
# 每个模型可以是一个单独的目录，也可以是某个目录下的二级子目录。
# 如果模型目录名称和 MODEL_PATH 中的 key 或 value 相同，程序会自动检测加载，无需修改 MODEL_PATH 中的路径。
MODEL_ROOT_PATH = "/mnt/ddata/models"

# 选用的 Embedding 名称   
EMBEDDING_MODEL = "bge-m3"

# Embedding模型是否通过服务启动（比如xinference、vllm）
EMBEDDING_SERVER = True

# Embedding 模型运行设备。设为"auto"会自动检测，也可手动设定为"cuda","mps","cpu"其中之一。
EMBEDDING_DEVICE = "auto"

# 如果需要在 EMBEDDING_MODEL 中增加自定义的关键字时配置
EMBEDDING_KEYWORD_FILE = "keywords.txt"
EMBEDDING_MODEL_OUTPUT_PATH = "output"

# 要运行的 LLM 名称，可以包括本地模型和在线模型。
# 第一个将作为 API 和 WEBUI 的默认模型
# LLM_MODELS = ['baichuan2-13b',"chatglm2-6b", "zhipu-api", "openai-api"]
LLM_MODELS = ['cc-13b-chat',"deepseek-r1","qwen"]

# AgentLM模型的名称 (可以不指定，指定之后就锁定进入Agent之后的Chain的模型，不指定就是LLM_MODELS[0])
Agent_MODEL = None

# LLM 运行设备。设为"auto"会自动检测，也可手动设定为"cuda","mps","cpu"其中之一。
LLM_DEVICE = "auto"

# 历史对话轮数
HISTORY_LEN = 3

# 大模型最长支持的长度，如果不填写，则使用模型默认的最大长度，如果填写，则为用户设定的最大长度
MAX_TOKENS = None

# LLM通用对话参数，越高越有创意
TEMPERATURE = 0.35
# TOP_P = 0.95 # ChatOpenAI暂不支持该参数

ONLINE_LLM_MODEL = {
    # 线上模型。请在server_config中为每个在线API设置不同的端口
    "cc-13b-chat": {
        "model_name": "glm-4",
        "api_base_url": "http://0.0.0.0:10006/v1",
        "api_key": "empty",
        "openai_proxy": "",
    },
    "deepseek-r1": {
        "model_name": "deepseek-r1",
        "api_base_url": "http://0.0.0.0:10008/v1",
        "api_key": "empty",
        "openai_proxy": "",
     },
    "qwen": {
        "model_name": "qwen",
        "api_base_url": "http://0.0.0.0:10007/v1",
        "api_key": "empty",
        "openai_proxy": "",
    }
}

# 在以下字典中修改属性值，以指定本地embedding模型存储位置。支持3种设置方法：
# 1、将对应的值修改为模型绝对路径
# 2、不修改此处的值（以 text2vec 为例）：
#       2.1 如果{MODEL_ROOT_PATH}下存在如下任一子目录：
#           - text2vec
#           - GanymedeNil/text2vec-large-chinese
#           - text2vec-large-chinese
#       2.2 如果以上本地路径不存在，则使用huggingface模型
MODEL_PATH = {
    "embed_model": {
        "bge-large-zh": "bge-large-zh-v1.5",
        "bge-large-zh-v2": "bge-large-zh-v2",
        "bge-large-zh-v3": "bge_test",
        "bge-m3": "bge-m3"
        #"nuclear_law_v1.2",
        # "text-embedding-ada-002": "your OPENAI_API_KEY",
    },

    "llm_model": {
        'cc-13b-chat': "glm-4-9b-chat",#"cc-13b-v1-5-AWQ",# "baichuan13b-base-sft-ds-qlora-all",#baichuan2-13b-base-sft-ds-qlora-all-AWQ #cc-13b-v1-5,'dct_exp/firefly-baichuan2-13b-chat-0403-contextQA-merge-11500',dct_exp/firefly-baichuan2-13b-chat-0403-contextQA-merge-11500 Baichuan2-13B-Chat-v2 Baichuan2-7B-Chat
    },
}

GENERATE_MODEL_SERVER={
    "model_name": "glm-4",
    "base_url" : "http://0.0.0.0:10006/v1",
    "api_key" : "EMPTY"
}

EMBEDDING_MODEL_SERVER={
    "model_name": "embed",
    "base_url" : "http://192.168.21.111:8105/v1",
    "api_key" : "cc"
}

RERANK_MODEL_SERVER={
    "model_name": "bge-reranker-v2-m3",
    "base_url" : "http://192.168.21.111:8106",
    "api_key" : "cc"
}
# 通常情况下不需要更改以下内容

# nltk 模型存储路径
NLTK_DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "nltk_data")

VLLM_MODEL_DICT = {
    'cc-13b-chat':'glm-4-9b-chat',
}

# 你认为支持Agent能力的模型，可以在这里添加，添加后不会出现可视化界面的警告
SUPPORT_AGENT_MODEL = [
    "openai-api",
    "chatglm3",
]
