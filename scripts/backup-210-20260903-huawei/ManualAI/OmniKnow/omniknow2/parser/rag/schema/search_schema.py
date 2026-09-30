
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict


class SearchModel(BaseModel):
    chunk_id: str = Field(..., description="ID")
    chunk_index: int = Field(..., description="index")
    content: str = Field(..., description="文字内容、表格的html内容、图片表格的caption")
    summary: str = Field(default="", description="摘要")
    file_id: str = Field(..., description="文件ID")
    file_path: str = Field(..., description="文件路径")
    media_path: str = Field(default="", description="图片路径、视频路径、图纸路径")
    chunk_source: str = Field(default="document", description="chunk的来源：document | image | video | audio | drawing | html")
    update_time: str = Field(..., description="更新时间")
    score: float = Field(..., description="chunk相似度分数")
    bbox_type: str = Field(default="text", description="边界框类型")
    bbox: List[Any] = Field(default_factory=list, description="边界框坐标")
    title: str = Field(default="", description="标题（图片、表格、文字）")
    cur_title: str = Field(default="", description="最近的标题")
    par_title: str = Field(default="", description="父级标题")
    page_idx: List[Any] = Field(default_factory=list, description="页码索引")
    collection_name: str = Field(default="", description="collection 来源")
    # others: str = Field(default="", description="其他扩展字段")
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



class SearchRequest(BaseModel):
    """解析请求模型"""
    query: str = Field(..., description="用户问题")
    collection_name: List[str] = Field(..., description="collection_name")
    top_k: int = Field(..., description="检索块的个数")
    threshold: float = Field(0.0, description="过滤分数")
    dense_type: str = Field("text", description="语义检索类型：text / summary / title")
    sparse_type: str = Field("text", description="关键字检索类型：text / summary / title")
    reranker_type: str = Field("weight", description="reranker类型：weight / rrf")
    dense_weight: float = Field(0.7, description="语义搜索的权重")
    sparse_weight: float = Field(0.3, description="关键字搜索的权重")
    rerank_model: bool = Field(False, description="是否使用rerank模型")


class SearchResponse(BaseModel):
    """查询响应模型"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="查询消息")
    chunks: List[SearchModel] = Field(default_factory=list, description="查询后的块列表")
    # total: int = Field(default=0, description="块总数")
