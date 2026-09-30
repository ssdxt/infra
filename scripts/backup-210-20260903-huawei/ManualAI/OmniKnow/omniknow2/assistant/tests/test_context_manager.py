import json

from langchain_core.messages import HumanMessage, ToolMessage

from src.utils.context_manager import validate_message_content


def test_validate_message_content_serializes_complex_content():
    messages = [
        HumanMessage(content={"topic": "解释", "locale": "zh-CN"}),
        HumanMessage(content=["a", "b"]),
    ]

    validated = validate_message_content(messages)

    assert validated[0].content == json.dumps(
        {"topic": "解释", "locale": "zh-CN"}, ensure_ascii=False
    )
    assert validated[1].content == json.dumps(["a", "b"], ensure_ascii=False)


def test_validate_message_content_falls_back_for_tool_message_errors():
    message = ToolMessage(content="ok", tool_call_id="call_123")
    delattr(message, "content")

    validated = validate_message_content([message])

    assert json.loads(validated[0].content)["error"]
