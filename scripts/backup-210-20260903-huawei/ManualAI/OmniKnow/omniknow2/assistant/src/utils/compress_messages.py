from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

def normalize_messages(messages):
    result = []

    for m in messages:
        if isinstance(m, HumanMessage):
            if m.content:
                result.append({"human": m.content})

        elif isinstance(m, AIMessage):
            if m.content:
                result.append({"ai": m.content})

        elif isinstance(m, SystemMessage):
            if m.content:
                result.append({"system": m.content})

    return result