from db.models.public import BaseModel
from training.schema import QusetionType

from sqlalchemy import Column, Integer, Text, Uuid, JSON, Enum, String, DateTime


# 课程
class Course(BaseModel):
    __tablename__ = 'courses'

    space_id = Column(Uuid, nullable=False, comment="空间ID")
    kbase_id = Column(Uuid, nullable=False, comment="关联知识库ID")
    title = Column(Text, nullable=False, comment="课程名称")
    description = Column(Text, comment="课程描述")
    status = Column(Integer, nullable=False, default=1, comment="课程状态，1-有效，0-无效")
    logo = Column(Text, comment="课程封面URL")
    resource_id = Column(Uuid, comment="关联文档ID")
    extra = Column(JSON, comment="额外信息，如考题数量等")


# 题库
class Questions(BaseModel):
    __tablename__ = 'questions'

    space_id = Column(Uuid, nullable=False, comment="空间ID")
    course_id = Column(Uuid, nullable=False, comment="课程ID")
    type = Column(Enum(QusetionType), nullable=False, comment="题目类型")
    stem = Column(Text, nullable=False, comment="题干")
    analysis = Column(Text, comment="解析")
    difficulty = Column(Integer, default=1, comment="难度等级, 1-5")
    default_score = Column(Integer, nullable=False, default=1, comment="默认分数")
    status = Column(Integer, nullable=False, default=1, comment="题目状态，1-有效，0-无效")
    extra = Column(JSON, comment="额外信息，如选项等")


class QuestionOptions(BaseModel):
    __tablename__ = 'question_options'

    question_id = Column(Uuid, nullable=False, comment="题目ID")
    option_key = Column(String(10), nullable=False, comment="选项标签，如A、B、C等")
    option_content = Column(Text, nullable=False, comment="选项内容")
    is_correct = Column(Integer, nullable=False, default=0, comment="是否正确选项，1-正确，0-错误")
    sort = Column(Integer, nullable=False, default=0, comment="选项排序")


class Paper(BaseModel):
    __tablename__ = 'papers'

    space_id = Column(Uuid, nullable=False, comment="空间ID")
    course_id = Column(Uuid, comment="课程ID")
    title= Column(Text, nullable=False, comment="试卷名称")
    description = Column(Text, comment="试卷描述")
    duration_minutes = Column(Integer, comment="考试时长，单位分钟")
    question_ids = Column(JSON, comment="题目ID列表")
    total_score = Column(Integer, nullable=False, default=0, comment="总分")
    status = Column(Integer, nullable=False, default=1, comment="试卷状态，1-有效，0-无效")


class PaperQuestions(BaseModel):
    __tablename__ = 'paper_questions'

    paper_id = Column(Uuid, nullable=False, comment="试卷ID")
    question_id = Column(Uuid, nullable=False, comment="题目ID")
    score = Column(Integer, nullable=False, default=1, comment="该题分数")
    sort = Column(Integer, nullable=False, default=0, comment="题目排序")
    section_name = Column(Enum(QusetionType), comment="题目所属部分名称，如单选题、填空题等")


# 考试记录表
class ExamSession(BaseModel):
    __tablename__ = 'exam_sessions'

    space_id = Column(Uuid, nullable=False, comment="空间ID")
    paper_id = Column(Uuid, nullable=False, comment="试卷ID")
    user_id = Column(Uuid, nullable=False, comment="用户ID")
    status = Column(String(32), nullable=False, default="not_started", comment="考试状态，not_started-未开始，ongoing-进行中，submitted-已提交，graded-已评分，timeout-已超时")
    start_time = Column(DateTime, comment="考试开始时间")
    submit_time = Column(DateTime, comment="考试提交时间")
    objective_score = Column(Integer, nullable=False, default=0, comment="客观题得分")
    subjective_score = Column(Integer, nullable=False, default=0, comment="主观题得分")
    total_score = Column(Integer, nullable=False, default=0, comment="总得分")
    snapshot_json = Column(JSON, comment="开考时试卷快照")
    evaluation = Column(Text, comment="AI 考试评价，Markdown 格式")


# 答案明细表
class ExamAnswer(BaseModel):
    __tablename__ = 'exam_answers'

    exam_session_id = Column(Uuid, nullable=False, comment="考试记录ID")
    question_id = Column(Uuid, nullable=False, comment="题目ID")
    question_type = Column(Enum(QusetionType), nullable=False, comment="题目类型")
    answer_text = Column(Text, comment="简答题答案 / 文本答案")
    answer_json = Column(JSON, comment="选择题、多选题结构化答案")
    is_correct = Column(Integer, comment="是否正确，1-正确，0-错误，null-未评判")
    score = Column(Integer, nullable=False, default=0, comment="得分")
    judge_status = Column(String(32), nullable=False, default='pending', comment="评判状态，pending-待评判，auto_graded-自动评判完成，manual_graded-人工评判完成")
    reviewer_id = Column(Uuid, comment="评审人ID")
    reviewed_at = Column(DateTime, comment="评审时间")
