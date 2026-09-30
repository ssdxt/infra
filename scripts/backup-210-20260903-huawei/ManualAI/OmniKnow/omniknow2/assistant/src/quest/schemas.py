from pydantic import AliasChoices, BaseModel, Field, field_validator


class QuestGenerateRequest(BaseModel):
    collection_name: str = Field(..., description="知识库 collection 名称")
    file_ids: list[str] = Field(
        ...,
        min_length=1,
        description="需要参与出题的文件 ID 列表",
    )

    @field_validator("collection_name")
    @classmethod
    def validate_collection_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("collection_name cannot be empty")
        return value

    @field_validator("file_ids")
    @classmethod
    def validate_file_ids(cls, value: list[str]) -> list[str]:
        cleaned_file_ids: list[str] = []
        seen: set[str] = set()

        for item in value:
            item_str = str(item).strip()
            if not item_str or item_str in seen:
                continue
            cleaned_file_ids.append(item_str)
            seen.add(item_str)

        if not cleaned_file_ids:
            raise ValueError("file_ids cannot be empty")

        return cleaned_file_ids


class QuestChatRequest(BaseModel):
    collection_name: str = Field(..., description="知识库 collection 名称")
    file_ids: list[str] = Field(
        ...,
        min_length=1,
        description="需要参与问答的文件 ID 列表",
    )
    query: str = Field(..., description="用户问题")
    thread_id: str = Field(
        "__default__",
        description="会话 ID；相同 thread_id 会复用短期记忆",
    )

    @field_validator("collection_name")
    @classmethod
    def validate_collection_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("collection_name cannot be empty")
        return value

    @field_validator("file_ids")
    @classmethod
    def validate_file_ids(cls, value: list[str]) -> list[str]:
        cleaned_file_ids: list[str] = []
        seen: set[str] = set()

        for item in value:
            item_str = str(item).strip()
            if not item_str or item_str in seen:
                continue
            cleaned_file_ids.append(item_str)
            seen.add(item_str)

        if not cleaned_file_ids:
            raise ValueError("file_ids cannot be empty")

        return cleaned_file_ids

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query cannot be empty")
        return value

    @field_validator("thread_id")
    @classmethod
    def validate_thread_id(cls, value: str) -> str:
        value = str(value or "").strip()
        return value or "__default__"


class QuestScoreRequest(BaseModel):
    exam_answer: str = Field(..., description="考生答案")
    standard_answer: str = Field(..., description="标准答案")

    @field_validator("exam_answer", "standard_answer")
    @classmethod
    def validate_answer_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("answer text cannot be empty")
        return value


class QuestEvaluationQuestion(BaseModel):
    title: str = Field(..., description="原文章节标题")
    question_type: str = Field(..., description="题目类型，选择或问答")
    question_name: str = Field(..., description="题目名称")
    options: list[str] = Field(default_factory=list, description="选择题选项")
    chunk_ids: list[str] = Field(default_factory=list, description="题目引用的 chunk_id 列表")
    student: list[int] | str | int = Field(..., description="考生答案")

    answer: list[int] | str | int = Field(..., description="标准答案")
    score: int = Field(..., description="得分，选择题 0/2，问答题 0 到 10")
    reason: str | None = Field(default=None, description="问答题判分理由")


class QuestEvaluationRecord(BaseModel):
    collection_name: str = Field(..., description="知识库 collection 名称")
    file_id: str = Field(..., description="来源文件 ID")
    file_name: str = Field(..., description="来源文件名称")
    title: str | None = Field(
        default=None,
        description="兼容旧结构的章节标题，优先使用 content 内每题的 title",
    )
    content: list[QuestEvaluationQuestion] = Field(
        ...,
        min_length=1,
        description="该章节下的答题记录",
    )


class RawQuestQuestion(BaseModel):
    question_type: str = Field(..., description="题目类型，只能是选择或问答")
    question_name: str = Field(..., description="题目描述")
    options: list[str] = Field(
        default_factory=list,
        description="选择题选项文本，问答题必须为空数组",
    )
    chunk_ids: list[str] | str = Field(
        default_factory=list,
        description="支撑该题的 chunk_id 列表",
    )
    answer: list[int] | str | int = Field(..., description="题目答案")


class RawQuestGeneration(BaseModel):
    questions: list[RawQuestQuestion] = Field(
        ...,
        min_length=5,
        max_length=8,
        description="题目列表，必须包含 4 道选择题和 1 道问答题",
    )


class QuestQuestion(BaseModel):
    question_type: str = Field(..., description="题目类型")
    question_name: str = Field(..., description="题目名称")
    options: list[str] = Field(default_factory=list, description="选择题选项")
    chunk_ids: list[str] = Field(default_factory=list, description="题目引用的 chunk_id 列表")
    answer: list[int] | str = Field(..., description="答案")


class QuestGenerateResponse(BaseModel):
    collection_name: str = Field(..., description="知识库 collection 名称")
    file_id: str = Field(..., description="本次出题命中的文件 ID")
    title: str = Field(..., description="本次随机命中的标题")
    content: list[QuestQuestion] = Field(
        ...,
        min_length=5,
        max_length=5,
        description="题目内容",
    )


class QuestChatReference(BaseModel):
    chunk_id: str = Field(..., description="命中的 chunk ID")
    file_id: str = Field(..., description="来源文件 ID")
    file_name: str = Field(..., description="来源文件名")
    title: str = Field(default="", description="命中的标题")
    score: float = Field(..., description="检索分数")
    page_idx: list[int] = Field(default_factory=list, description="命中的页码列表")


class QuestChatResponse(BaseModel):
    answer: str = Field(..., description="基于指定文件范围生成的回答")
    references: list[QuestChatReference] = Field(
        default_factory=list,
        description="回答引用的知识片段",
    )


class RawQuestScore(BaseModel):
    score: int = Field(..., description="0 到 10 的整数评分")
    reason: str = Field(..., description="50 字以内的判分理由")


class QuestScoreResponse(BaseModel):
    score: int = Field(..., ge=0, le=10, description="0 到 10 的整数评分")
    reason: str = Field(..., max_length=50, description="50 字以内的判分理由")


class QuestEvaluationChapterSummary(BaseModel):
    file_name: str = Field(..., description="来源文件名称")
    title: str = Field(..., description="章节标题")
    total_questions: int = Field(..., description="章节题目数")
    score_obtained: float = Field(..., description="章节已得分")
    score_possible: float = Field(..., description="章节满分")
    score_rate: float = Field(..., description="章节得分率，0 到 1")


class QuestEvaluationScoreSummary(BaseModel):
    total_questions: int = Field(..., description="总题目数")
    total_score_obtained: float = Field(..., description="总得分")
    total_score_possible: float = Field(..., description="总满分")
    score_rate: float = Field(..., description="总得分率，0 到 1")
    choice_total: int = Field(..., description="选择题总数")
    choice_correct: int = Field(..., description="选择题答对数")
    choice_accuracy: float = Field(..., description="选择题正确率，0 到 1")
    qa_total: int = Field(..., description="问答题总数")
    qa_average_score: float = Field(..., description="问答题平均分，0 到 10")
    chapter_performance: list[QuestEvaluationChapterSummary] = Field(
        default_factory=list,
        description="按章节统计的得分表现",
    )


def build_question_payload(
    question_type: str,
    question_name: str,
    options: list[str],
    chunk_ids: list[str],
    answer: list[int] | str,
) -> QuestQuestion:
    return QuestQuestion(
        question_type=question_type,
        question_name=question_name,
        options=options,
        chunk_ids=chunk_ids,
        answer=answer,
    )
