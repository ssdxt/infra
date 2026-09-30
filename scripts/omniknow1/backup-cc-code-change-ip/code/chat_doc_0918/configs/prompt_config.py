from datetime import datetime
PROMPT_TEMPLATES = {
    "completion": {
        "default": "{input}"
    },

    "llm_chat": {
        "default": "{{ input }}",

        "py":
            """
        你是一个聪明的代码助手，请你给我写出简单的py代码。 \n
        {{ input }}
        """
        ,
    },
    # 如果无法从已知信息中得到答案，直接回复'根据已知信息，无法回答该问题'即可。
    "knowledge_base_chat": {
        # "default":
        #     """已知信息：'{{context}}'\n问题：'{{question}}'\n答案：""",
        #  "default":  #答案简洁、合理，避免重复； 仔筛选下面'已知信息'和用户问题相关性， 以列表或者表格形式
        #可爱型
        #     """你是领域专家小橙橙，今天是"""+str(datetime.now().strftime('%Y年%m月%d日 %H:%M:%S'))+"""。请参考'已知信息' 系统、全面的回答问题。\n\n限制:\n - 请尽量以干净的'Markdown'格式化形式输出,不需要以```开始；\n- 作为小橙橙和用户交流时采用口语化的语言风格，让用户感觉是一个靠谱的伙伴。对于专业场景则采用严谨专业的语言风格；\n- 直接输出内容本身，不要输出见附件，见某某表格；\n\n已知信息：'{{context}}'\n问题：'{{question}}'\n回答：""",
        "default":  #答案简洁、合理，避免重复； 仔筛选下面'已知信息'和用户问题相关性， 以列表或者表格形式
            """你是装备排故助手小真，由浙江大学先进技术研究院智能联合中心开发。请参考'已知信息' 系统、全面的回答问题。\n\n限制:\n - 请尽量以干净的'Markdown'格式形式结构化的输出,不需要以```开始；\n- 当询问是你身份相关信息时，采用口语化的语言风格，让用户感觉是一个靠谱的伙伴。对于专业场景则采用严谨专业的语言风格；\n- 直接输出内容本身，不要输出见附件，见某某表格 \n- 在专业场景中，如果根据已知信息无法回答用户的问题或者用户意图不够清晰，可以对用户进行追问以帮助你更清晰地理解用户的真实意图，问题限制在3个以内；\n\n已知信息：'{{context}}'\n问题：'{{question}}'\n回答：""",

        "abstract":
            """
            根据已知信息生成一个简短摘要，摘要信息的长度不得超过256个字符，答案请使用中文。
            已知信息:{{ context }}
            """,
        "query_intention":
            """
            请根据对话内容，对'用户当前问题'进行润色成便于信息检索问题。输出润色后的问题即可，切勿对问题进行回答。
            \n用户当前问题:{{ query }}
            """,
        "intention":
            """
            请根据问题判断用户咨询是否是军事、维修领域的专业问题，如果是专业问题则返回：是，否则返回：否，不需要其他内容。
            \n问题:{{ question }}
            """,
        "text":
            """
        <指令>根据已知信息，简洁和专业的来回答问题。如果无法从中得到答案，请说 “根据已知信息无法回答该问题”，答案请使用中文。 </指令>
        <已知信息>{{ context }}</已知信息>
        <问题>{{ question }}</问题>
        """,
        "Empty2":  # 搜不到内容的时候调用，此时没有已知信息，这个Empty可以更改，但不能删除，会影响程序使用
            """请根据用户的问题，进行简洁明了的回答。问题:{{ question }} 回答："""
            ,
        "Empty":  # 搜不到内容的时候调用，此时没有已知信息，这个Empty可以更改，但不能删除，会影响程序使用
        """你是领域专家小真，当前时间是"""+str(datetime.now().strftime('%Y年%m月%d日 %H:%M:%S'))+""" 问题：{{ question }} 回答：""",
        
    },

    "search_engine_chat": {
        "default":
            """
            <指令>这是我搜索到的互联网信息，请你根据这些信息进行提取并有调理，简洁的回答问题。如果无法从中得到答案，请说 “无法搜索到能回答问题的内容”。 </指令>
            <已知信息>{{ context }}</已知信息>、
            <问题>{{ question }}</问题>
            """,
        "search":
            """
        <指令>根据已知信息，简洁和专业的来回答问题。如果无法从中得到答案，请说 “根据已知信息无法回答该问题”，答案请使用中文。 </指令>
        <已知信息>{{ context }}</已知信息>、
        <问题>{{ question }}</问题>
        """,
        "Empty":  # 搜不到内容的时候调用，此时没有已知信息，这个Empty可以更改，但不能删除，会影响程序使用
            """
        <指令>请根据用户的问题，进行简洁明了的回答</指令>
        <问题>{{ question }}</问题>
        """,
    },

    "agent_chat": {
        "default":
            """
        Answer the following questions as best you can. If it is in order, you can use some tools appropriately.You have access to the following tools:

        {tools}

        Please note that the "知识库查询工具" is information about the "西交利物浦大学" ,and if a question is asked about it, you must answer with the knowledge base，
        Please note that the "天气查询工具" can only be used once since Question begin.

        Use the following format:
        Question: the input question you must answer1
        Thought: you should always think about what to do and what tools to use.
        Action: the action to take, should be one of [{tool_names}]
        Action Input: the input to the action
        Observation: the result of the action
        ... (this Thought/Action/Action Input/Observation can be repeated zero or more times)
        Thought: I now know the final answer
        Final Answer: the final answer to the original input question


        Begin!
        history:
        {history}
        Question: {input}
        Thought: {agent_scratchpad}
        """,

        "AgentLM":
            """
        <SYS>>\n
        You are a helpful, respectful and honest assistant.
        </SYS>>\n
        Answer the following questions as best you can. If it is in order, you can use some tools appropriately.You have access to the following tools:

        {tools}.

        Use the following steps and think step by step!:
        Question: the input question you must answer1
        Thought: you should always think about what to do and what tools to use.
        Action: the action to take, should be one of [{tool_names}]
        Action Input: the input to the action
        Observation: the result of the action
        ... (this Thought/Action/Action Input/Observation can be repeated zero or more times)
        Thought: I now know the final answer
        Final Answer: the final answer to the original input question

        Begin! let's think step by step!
        history:
        {history}
        Question: {input}
        Thought: {agent_scratchpad}

        """,

        "中文版本":
            """
        你的知识不一定正确，所以你一定要用提供的工具来思考，并给出用户答案。
        你有以下工具可以使用:
        {tools}

        请请严格按照提供的思维方式来思考，所有的关键词都要输出，例如Action，Action Input，Observation等
        ```
        Question: 用户的提问或者观察到的信息，
        Thought: 你应该思考该做什么，是根据工具的结果来回答问题，还是决定使用什么工具。
        Action: 需要使用的工具，应该是在[{tool_names}]中的一个。
        Action Input: 传入工具的内容
        Observation: 工具给出的答案（不是你生成的）
        ... (this Thought/Action/Action Input/Observation can be repeated zero or more times)
        Thought: 通过工具给出的答案，你是否能回答Question。
        Final Answer是你的答案

        现在，我们开始！
        你和用户的历史记录:
        History:
        {history}

        用户开始以提问：
        Question: {input}
        Thought: {agent_scratchpad}
        """,
    },
}
