from typing import List, Optional, Union

from pydantic import BaseModel, Field

from src.config.report_style import ReportStyle
from src.subagents.rag.retriever import Resource


class ContentItem(BaseModel):
    type: str = Field(..., description="The type of content (text, image, etc.)")
    text: Optional[str] = Field(None, description="The text content if type is 'text'")
    image_url: Optional[str] = Field(
        None, description="The image URL if type is 'image'"
    )


class ChatMessage(BaseModel):
    role: str = Field(
        ..., description="The role of the message sender (user or assistant)"
    )
    content: Union[str, List[ContentItem]] = Field(
        ...,
        description="The content of the message, either a string or a list of content items",
    )


class ChatRequest(BaseModel):
    messages: Optional[List[ChatMessage]] = Field(
        default_factory=list,
        description="History of messages between the user and the assistant",
    )
    resources: Optional[List[Resource]] = Field(
        default_factory=list,
        description="Resources to be used for the research",
    )
    debug: Optional[bool] = Field(False, description="Whether to enable debug logging")
    thread_id: Optional[str] = Field(
        "__default__", description="A specific conversation identifier"
    )
    locale: Optional[str] = Field(
        "en-US", description="Language locale for the conversation (e.g., en-US, zh-CN)"
    )
    max_plan_iterations: Optional[int] = Field(
        1, description="The maximum number of plan iterations"
    )
    max_step_num: Optional[int] = Field(
        3, description="The maximum number of steps in a plan"
    )
    max_search_results: Optional[int] = Field(
        3, description="The maximum number of search results"
    )
    auto_accepted_plan: Optional[bool] = Field(
        False, description="Whether to automatically accept the plan"
    )
    interrupt_feedback: Optional[str] = Field(
        None, description="Interrupt feedback from the user on the plan"
    )
    mcp_settings: Optional[dict] = Field(
        None, description="MCP settings for the chat request"
    )
    enable_background_investigation: Optional[bool] = Field(
        True, description="Whether to get background investigation before plan"
    )
    report_style: Optional[ReportStyle] = Field(
        ReportStyle.ACADEMIC, description="The style of the report"
    )
    enable_deep_thinking: Optional[bool] = Field(
        False, description="Whether to enable deep thinking"
    )
    enable_clarification: Optional[bool] = Field(
        None,
        description="Whether to enable multi-turn clarification (default: None, uses State default=False)",
    )
    max_clarification_rounds: Optional[int] = Field(
        None,
        description="Maximum number of clarification rounds (default: None, uses State default=3)",
    )
    interrupt_before_tools: List[str] = Field(
        default_factory=list,
        description="List of tool names to interrupt before execution (e.g., ['db_tool', 'api_tool'])",
    )
    image_url: Optional[str] = Field(
        None,
        description="File path of image that uploaded from frontend.",
    )
    user_id: Optional[str] = Field(
        "anonymous", description="A specific user uuid identifier"
    )
    enable_longterm_memory: Optional[bool] = Field(
        None,
        description="Whether to enable longterm memory (default: None, uses State default=False)",
    )
    llm_type: Optional[str] = Field(
        "basic",
        description="Runtime-selected LLM type for this request.",
    )


class NeoChatRequest(BaseModel):
    messages: Optional[List[ChatMessage]] = Field(
        default_factory=list,
        description="History of messages between the user and the assistant",
    )
    resources: Optional[List[Resource]] = Field(
        default_factory=list,
        description="Resources to be used for the research",
    )
    thread_id: Optional[str] = Field(
        "__default__", description="A specific conversation identifier"
    )
    locale: Optional[str] = Field(
        "en-US", description="Language locale for the conversation (e.g., en-US, zh-CN)"
    )
    mcp_settings: Optional[dict] = Field(
        None, description="MCP settings for the chat request"
    )
    image_url: Optional[str] = Field(
        None,
        description="File path of image that uploaded from frontend.",
    )
    user_id: Optional[str] = Field(
        "anonymous", description="A specific user uuid identifier"
    )
    enable_longterm_memory: Optional[bool] = Field(
        None,
        description="Whether to enable longterm memory (default: None, uses State default=False)",
    )
    llm_type: Optional[str] = Field(
        "basic",
        description="Runtime-selected LLM type for this request.",
    )


class NeoTitleSummaryRequest(BaseModel):
    messages: List[ChatMessage] = Field(
        ..., description="History of messages between the user and the assistant"
    )
    locale: Optional[str] = Field(
        "zh-CN", description="Language locale for the conversation (e.g., en-US, zh-CN)"
    )
    llm_type: Optional[str] = Field(
        "basic",
        description="Runtime-selected LLM type for this request.",
    )


class TTSRequest(BaseModel):
    text: str = Field(..., description="The text to convert to speech")
    voice_type: Optional[str] = Field(
        "BV700_V2_streaming", description="The voice type to use"
    )
    encoding: Optional[str] = Field("mp3", description="The audio encoding format")
    speed_ratio: Optional[float] = Field(1.0, description="Speech speed ratio")
    volume_ratio: Optional[float] = Field(1.0, description="Speech volume ratio")
    pitch_ratio: Optional[float] = Field(1.0, description="Speech pitch ratio")
    text_type: Optional[str] = Field("plain", description="Text type (plain or ssml)")
    with_frontend: Optional[int] = Field(
        1, description="Whether to use frontend processing"
    )
    frontend_type: Optional[str] = Field("unitTson", description="Frontend type")
