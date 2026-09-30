from sqlalchemy import (Column,
                        Integer,
                        String,
                        JSON,
                        Text,
                        Uuid,
                        Enum,
                        DATE,
                        Boolean,
                        BigInteger)

from db.models.public import BaseModel
from schemas.kbase import KbaseStatus
from core.acl.schema import ResourceType, ResourceStatus
from utils.public import generate_uuid7


class Tenant(BaseModel):
    __tablename__ = 'tenant'

    name = Column(String(255), nullable=False, comment="租户名称")
    md5 = Column(String(255), nullable=False, comment="MD5")
    description = Column(Text, comment="描述")
    logo = Column(Text, comment="图标")
    contact = Column(String(20), comment="联系人")
    status = Column(Integer, nullable=False, default=1, comment="租户状态")
    version = Column(Integer, nullable=False, default=0, comment="版本信息：免费版：0 基础版：1 专业版：2 企业版：3")


# user_space_mapping = Table(
#     'user_space_mapping',
#     Base.metadata,
#     Column('user_id', Uuid, ForeignKey('user.uuid'), primary_key=True,
#             nullable=False, comment="用户ID"),
#     Column('space_id', Uuid, ForeignKey('space.uuid'), primary_key=True,
#             nullable=False, comment="空间ID"),
#     Column('role', String(255), nullable=False, default='member', comment="用户在空间中的角色")
# )


class Space(BaseModel):
    __tablename__ = 'space'

    name = Column(String(255), nullable=False, comment="名称")
    description = Column(Text, comment="描述")
    logo = Column(Text, comment="图标")
    status = Column(Integer, nullable=False, default=1, comment="状态")
    owner = Column(Uuid, nullable=False, comment="所属用户")
    code = Column(String(255), nullable=False, comment="唯一标识符")

    # users = relationship(
    #     "User",
    #     secondary=user_space_mapping,
    #     back_populates="spaces",
    #     lazy="selectin",
    # )

# class SpaceUserMapping(BaseModel):
#     __tablename__ = 'space_user_mapping'
#
#     space_id = Column(Uuid, ForeignKey('space.uuid'), nullable=False, comment="空间ID")
#     user_id = Column(Uuid, ForeignKey('user.uuid'), nullable=False, comment="用户ID")


class User(BaseModel):
    __tablename__ = 'user'

    name = Column(String(255), nullable=False, comment="姓名")
    account = Column(String(255), nullable=False, unique=True, comment="账号")
    password = Column(String(255), nullable=False, comment="密码")
    salt = Column(String(255), nullable=False, comment="密码盐")
    status = Column(Integer, nullable=False, default=1, comment="用户状态")
    role = Column(Integer, nullable=False, default=2, comment="用户角色,超管:0,管理员:1,普通用户:2")
    source = Column(Enum("超真云", "本地注册", "管理员注册", name="user_source_enum"), nullable=False, default="本地注册", comment="用户来源")
    space_id = Column(Uuid, nullable=True, comment="所属空间ID")
    space_role = Column(
        Enum("owner", "admin", "member", "viewer", name="user_space_role_enum"),
        nullable=True,
        default="member",
        comment="用户在空间中的角色：owner/admin/member/viewer",
    )


class UserDetail(BaseModel):
    __tablename__ = 'user_detail'

    user_id = Column(Uuid, nullable=False, comment="用户ID")
    phone = Column(String(11), nullable=True, unique=True, comment="手机号")
    email = Column(String(255), nullable=True, unique=True, comment="邮箱")
    ent_id = Column(Uuid, nullable=True, comment="企业ID")
    department_id = Column(Uuid, nullable=True, comment="部门ID")
    position_id = Column(Uuid, nullable=True, comment="职位ID")
    birthday = Column(DATE, nullable=True, comment="生日")
    sex = Column(Integer, nullable=False, default=0, comment="性别,女:1;男:2;未知:0")

    # def to_dict(self):
    #     return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class Department(BaseModel):
    __tablename__ = 'department'

    ent_id = Column(Uuid, nullable=False, comment="租户ID")
    name = Column(String(255), nullable=False, comment="部门名称")
    description = Column(Text, comment="部门描述")
    status = Column(Integer, nullable=False, default=1, comment="部门状态")


class Position(BaseModel):
    __tablename__ = 'position'

    ent_id = Column(Uuid, nullable=False, comment="企业ID")
    name = Column(String(255), nullable=False, comment="职位名称")
    description = Column(Text, comment="职位描述")
    status = Column(Integer, nullable=False, default=1, comment="职位状态")
    department_id = Column(Uuid, comment="部门ID")


class Agent(BaseModel):
    __tablename__ = 'agent'

    name = Column(String(255), nullable=False, comment="名称")
    logo = Column(Text, comment="图片路径")
    description = Column(Text, comment="描述")
    kb_list = Column(JSON, comment="知识库列表")
    model_list = Column(JSON, comment="模型列表")
    prologue = Column(Text, comment="开场白")
    questions = Column(JSON, comment="问题集")
    voice = Column(Boolean, nullable=False, default=False, comment="是否语音")
    asr = Column(String(255), comment="语音识别模型")
    tts = Column(String(255), comment="语音合成模型")


class KnowledgeBase(BaseModel):
    __tablename__ = 'knowledge_base'

    name = Column(String(255), nullable=False, comment="名称")
    collection_name = Column(String(255), nullable=False, comment="向量集合名称")
    logo = Column(Text, comment="图片路径")
    tag = Column(JSON, comment="标签")
    default_questions = Column(JSON, comment="默认问题列表")
    chat_resources = Column(JSON, comment="聊天资源列表")
    description = Column(Text, comment="描述")
    status = Column(Enum(KbaseStatus), nullable=False, default=KbaseStatus.active, comment="状态")
    public = Column(Boolean, nullable=False, default=False, comment="是否公开")
    embed = Column(String(255), nullable=False, comment="嵌入模型")
    user_id = Column(Uuid, nullable=False, comment="归属用户")
    space_id = Column(Uuid, nullable=False, comment="归属空间")


class Chunk(BaseModel):
    __tablename__ = 'chunk'

    space_id = Column(Uuid, nullable=False, comment="空间ID")
    kbase_id = Column(Uuid, nullable=False, comment="知识库ID")
    doc_id = Column(Uuid, nullable=False, comment="文件ID")
    chunk_id = Column(String(255), nullable=False, comment="分块ID")
    content = Column(Text, comment="原始数据")
    index = Column(Integer, comment="分块索引")
    bbox_type = Column(String(50), comment="边界框类型")
    title = Column(Text, comment="标题")
    summary = Column(Text, comment="摘要")
    media_path = Column(Text, comment="媒体路径")
    bbox = Column(JSON, comment="边界框坐标")
    page_idx = Column(JSON, comment="页码索引")
    others = Column(JSON, comment="其他信息")
    source = Column(String(50), comment="分块来源")


class Resource(BaseModel):
    __tablename__ = 'resource'

    # --- 通用字段 ---
    name = Column(String(255), nullable=False, comment="资源名称")
    description = Column(Text, nullable=True, comment="资源描述")
    type = Column(Enum(ResourceType, native_enum=False, name="resource_type_enum"), nullable=False, comment="资源类型")
    path = Column(Text, nullable=True, comment="资源路径（文档类型时为源文件 OSS 路径）")
    link = Column(Text, nullable=True, comment="资源链接")
    object = Column(Text, nullable=True, comment="资源对象")
    size = Column(BigInteger, nullable=True, comment="资源大小")
    md5 = Column(String(255), nullable=True, comment="资源MD5值")
    status = Column(Enum(ResourceStatus), nullable=False, default=ResourceStatus.pending, comment="资源状态")
    owner_id = Column(Uuid, nullable=False, comment="资源拥有者ID")
    space_id = Column(Uuid, nullable=False, comment="资源所属空间ID")
    kbase_id = Column(Uuid, nullable=True, comment="关联知识库ID")
    rag_config = Column(JSON, nullable=True, comment="RAG配置")

    # --- 文档类型专属字段（type=doc 时有值） ---
    content = Column(Text, nullable=True, comment="原始内容（Markdown 等）")
    doc_metadata = Column(JSON, nullable=True, comment="文档元数据")
    logo = Column(Text, nullable=True, comment="封面路径")
    processed_oss_path = Column(Text, nullable=True, comment="转换后文档 OSS 路径")
    file_type = Column(String(255), nullable=True, comment="文件扩展名类型")
    chunk_size = Column(Integer, nullable=True, default=0, comment="分块数量")
    summary = Column(Text, nullable=True, comment="文档摘要")
    # process_status = Column(Enum(ProcessStatus), nullable=True, default="pending", comment="解析状态")
    tag = Column(JSON, nullable=True, comment="文件标签")
    source = Column(String(255), nullable=True, comment="文件来源")
    identification_method = Column(String(255), nullable=True, comment="识别方式")
    block_strategy = Column(String(255), nullable=True, comment="分块策略")
    index_strategy = Column(String(255), nullable=True, comment="索引策略")


class Conversation(BaseModel):
    __tablename__ = 'conversation'

    uuid = Column(String(36), primary_key=True, unique=True, nullable=False, default=generate_uuid7, comment="会话UUID")
    space_id = Column(Uuid, nullable=False, comment="空间ID")
    kbase_ids = Column(JSON, nullable=True, comment="知识库ID")
    user_id = Column(Uuid, nullable=False, comment="用户ID")
    agent_id = Column(Uuid, nullable=True, comment="智能体ID")
    title = Column(String(255), nullable=False, comment="会话标题")
    status = Column(Enum("active", "deleted", name="conversation_status_enum"), nullable=False, default="active", comment="会话状态")
    counter = Column(Integer, nullable=False, default=0, comment="消息计数器")
    meta = Column(JSON, comment="会话元信息")


class ChatMessage(BaseModel):
    __tablename__ = 'chat_message'

    uuid = Column(String(36), primary_key=True, unique=True, nullable=False, default=generate_uuid7, comment="消息UUIDv7")
    space_id = Column(Uuid, nullable=False, comment="空间ID")
    conversation_id = Column(String(36), nullable=False, comment="会话ID")
    role = Column(Enum("user", "agent", name="chat_message_role_enum"), nullable=False, comment="消息角色")
    content = Column(Text, nullable=False, comment="消息内容")
    text = Column(Text, nullable=True, comment="消息文本内容（去除格式）")
    preview = Column(String(255), comment="消息预览，前50个字符")
    status = Column(Enum("active", "deleted", name="chat_message_status_enum"), nullable=False, default="active", comment="消息状态")
    timestamp = Column(BigInteger, nullable=False, comment="消息时间戳")
    is_vectorized = Column(Boolean, nullable=False, default=False, comment="是否已向量化")


class DefaultQuestion(BaseModel):
    __tablename__ = 'default_question'

    space_id = Column(Uuid, nullable=False, comment="空间ID")
    kbase_id = Column(Uuid, nullable=False, comment="知识库ID")
    question = Column(Text, nullable=False, comment="默认问题")
    order = Column(Integer, nullable=False, default=0, comment="排序字段，数值越小优先级越高")


class ChatResource(BaseModel):
    __tablename__ = 'chat_resource'

    space_id = Column(Uuid, nullable=False, comment="空间ID")
    uri = Column(String(225), nullable=False, comment="资源ID")
    title = Column(String(255), nullable=False, comment="资源标题")
    description = Column(Text, comment="资源描述")
    agent = Column(String(255), comment="关联智能体")
