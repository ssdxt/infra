from pydantic import BaseModel, Field
from uuid import UUID
from enum import Enum


class KBaseCreateSchema(BaseModel):
    name: str | None = Field(...,
                            description="知识库名称")
    description: str | None = Field(None,description="知识库描述")
    logo: str | None = Field(None,description="知识库Logo URL")
    public: bool = Field(False,description="知识库是否公开")
    embed: str = Field(..., description="知识库嵌入模型")
    tags: list[str] | None = Field(None, description="知识库标签列表")
    collection_name: str | None = Field(None, description="知识库向量存储集合名称")


class KBaseUpdateSchema(BaseModel):
    name: str | None = Field(None,
                            description="知识库名称")
    description: str | None = Field(None,description="知识库描述")
    logo: str | None = Field(None,description="知识库Logo URL")
    public: bool | None = Field(None,description="知识库是否公开")
    default_questions: list | None = Field(None, description="知识库默认问题列表")
    chat_resources: list | None = Field(None, description="知识库对话资源列表")


class ParseOptions(BaseModel):
    """
    文档解析参数配置（唯一定义源）。

    新增解析参数只需在此声明并设置默认值，
    服务层和任务队列会自动透传，无需修改其他代码。
    """
    # --- 分块参数 ---
    max_chunk_size: int = Field(1024, description="最大分块大小")
    chunk_overlap: int = Field(0, description="分块重叠大小")
    delimiters: list[str] = Field(default_factory=lambda: ["\n\n", "\n", " ", ""], description="分块分隔符列表")

    # --- 解析能力开关 ---
    summary: bool = Field(False, description="是否生成chunk摘要")
    backend: str = Field("pipeline", description="后端处理模型")
    table: bool = Field(True, description="是否解析表格数据")
    parent_titles: bool = Field(True, description="是否追踪父标题")
    start_page: int = Field(0, description="解析起始页")
    end_page: int = Field(99999, description="解析结束页")
    title_correction: bool = Field(True, description="是否进行文档总结")
    method : str = Field("smart", description="解析方式")


class DocParseRequest(BaseModel):
    """文档解析请求体"""
    doc_ids: list[UUID] = Field(..., description="文件ID列表")
    parse_config: ParseOptions = Field(default_factory=ParseOptions, description="解析配置，不传则使用默认值")


class MarkdownUploadSchema(BaseModel):
    uuid: UUID | None = Field(None, description="Markdown文件ID，新增时可不传，更新时必传")
    name: str = Field(..., description="Markdown文件名称")
    content: str = Field(..., description="Markdown文件内容")


class KbaseStatus(str, Enum):
    active = "active"
    deleted = "deleted"


class QuestionCreate(BaseModel):
    content: str = Field(..., description="问题内容")
    order: int = Field(..., ge=0, description="问题顺序，整数，越小越靠前")


class DefaultQuestionCreateSchema(BaseModel):
    questions: list[QuestionCreate] = Field(..., description="默认问题列表")

