from pathlib import Path
from typing import Dict, Any, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


class ChunkModel(BaseModel):
    """文档解析块返回类型"""
    chunk_id: str = Field(..., description="ID")
    chunk_index: int = Field(..., description="index")
    content: str = Field(..., description="文字内容、图、表的capture")
    file_id: str = Field(..., description="文件ID")
    file_path: str = Field(..., description="文件路径")
    update_time: str = Field(..., description="更新时间")
    bbox_type: str = Field(default="text", description="边界框类型")
    title: str = Field(default="", description="文字的标题、图片表格的caption")
    cur_title: str = Field(default="", description="最近的标题")
    par_title: str = Field(default="", description="父级标题")
    summary: str = Field(default="", description="摘要")
    media_path: str = Field(default="", description="图片路径、视频路径、图纸路径")
    chunk_source: str = Field(default="document", description="chunk的来源：document | image | video | audio | drawing | html")
    bbox: List[Any] = Field(default_factory=list, description="边界框坐标")
    page_idx: List[Any] = Field(default_factory=list, description="页码索引")

    others: Dict[str, Any] = Field(
        default_factory=dict,
        description="其他扩展字段"
    )

    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式（兼容原有代码）
        使用 model_dump() 方法，包含所有字段和额外字段
        """
        return self.model_dump(include=None, exclude_none=False)


class ImageModel(BaseModel):
    """文档解析块返回类型"""
    chunk_id: str = Field(..., description="ID")
    kb_id: str = Field(..., description="知识库ID")
    img_id: str = Field(..., description="图片ID")
    media_path: str = Field(default="", description="图片路径")
    source_media_path: str = Field(default="", description="源媒体路径")
    others: Dict[str, Any] = Field(
        default_factory=dict,
        description="其他扩展字段"
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式（兼容原有代码）
        使用 model_dump() 方法，包含所有字段和额外字段
        """
        return self.model_dump(include=None, exclude_none=False)


class ParseRequest(BaseModel):
    """解析请求模型"""
    file_id: str = Field(..., description="文件ID")
    file_path: str = Field(..., description="文件路径")
    summary: bool = Field(False, description="chunk总结是否开启")
    method: Optional[Literal["normal", "smart"]] = Field(
        "smart", description="可选的解析方法：normal 或 smart"
    )
    output_dir: str = Field("/mnt/ddata2/cc007/omniknow2/parser/rag/mineru_output", description="输出目录")
    chunk_source: str = Field("document", description="chunk的来源：document | image | video | audio | drawing | html")
    backend: str = Field("pipeline", description="pipeline")
    formula: bool = Field(False, description="是否启用公式")
    table: bool = Field(True, description="是否启用表格")
    vlm_url: str = Field("http://127.0.0.1:8406", description="vlm接口地址")
    chunk_size: int = Field(1024, description="chunk块大小")
    chunk_overlap: int = Field(0, description="chunk块重叠")
    delimiters: List[Any] = Field(["\n\n", "\n", "。", "；", "，", " ", "!", "！","?","？"], description="分隔符")
    include_parent_titles: bool = Field(True, description="是否启用连续上级标题")
    start_page: int = Field(1, description="开始页")
    end_page: int = Field(99999, description="结束页")
    title_correction: bool = Field(True, description="标题修正是否开启")


class ParseResponse(BaseModel):
    """解析响应模型"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="消息")
    doc_summary: str = Field("", description="解析后的章节总结列表")
    data: List[ChunkModel] = Field(default_factory=list, description="解析后的块列表")
    
    # total: int = Field(default=0, description="块总数")


class ConvertRequest(BaseModel):
    """解析请求模型"""
    file_path: Union[str, Path] = Field(..., description="文件路径")
    output_dir: str = Field("/mnt/ddata2/cc007/omniknow2/parser/rag/convert_document", description="输出目录")

class ConvertResponse(BaseModel):
    """解析请求模型"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="消息")
    file_path: str = Field(..., description="文件路径")
    

class UploadRequest(BaseModel):
    """上传请求模型"""
    chunks: List[ChunkModel] = Field(..., description="块列表")
    collection_name: str = Field(..., description="collection_name=知识库ID")
    img_collection_name: str = Field("images2", description="图片知识库ID")
    sum_collection_name: str = Field("chapter_summary", description="摘要知识库ID")
    # title_correction: bool = Field(True, description="标题修正是否开启")
    doc_summary: str = Field(..., description="文档摘要")

    


class UploadResponse(BaseModel):
    """解析响应模型"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="消息")
    # chunks: List[ChunkModel] = Field(default_factory=list, description="解析后的块列表")
    # total: int = Field(default=0, description="块总数")
    

class ImgUploadRequest(BaseModel):
    """上传请求模型"""
    chunks: List[ImageModel] = Field(..., description="块列表")
    img_collection_name: str = Field(..., description="collection_name=知识库ID")

class Message(BaseModel):
    role: str
    content: str

class MemoryUploadRequest(BaseModel):
    """记忆上传请求模型"""
    collection_name: str = Field(..., description="collection_name=知识库ID")
    messages: List[Message] = Field(..., description="消息内容")
    user_id: str = Field(..., description="用户id")
    thread_id: str = Field(..., description="会话id")
    update_time: str = Field(..., description="更新时间")
    

class MemoryDeleteRequest(BaseModel):
    """记忆删除模型"""
    collection_name: str = Field("long_memory", description="collection_name=知识库ID")
    user_id: str = Field(..., description="用户id")
    thread_id: str = Field(..., description="会话id")
    

class DocDeleteRequest(BaseModel):
    """文档删除模型"""
    collection_name: str = Field("", description="collection_name=知识库ID")
    file_id: str = Field(..., description="文件id")
    chunk_id: Optional[str] = Field(
        "",
        description="块ID（可选；不传则删除整个文件下所有 chunk）"
    )


class CollectionDeleteRequest(BaseModel):
    collection_name: str = Field("", description="collection_name=知识库ID")
    
    

