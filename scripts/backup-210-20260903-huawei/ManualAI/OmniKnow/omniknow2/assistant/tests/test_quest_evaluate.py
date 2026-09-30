from src.quest.schemas import QuestEvaluationQuestion
from src.quest.service import QuestService


def test_quest_evaluation_question_accepts_student_alias():
    question = QuestEvaluationQuestion(
        title="第一章",
        question_type="选择",
        question_name="这是题目",
        options=["选项A", "选项B", "选项C", "选项D"],
        chunk_ids=["chunk-1"],
        student=[],
        answer=[0],
        score=0,
    )

    assert question.student == []
    assert question.model_dump(by_alias=True)["student"] == []

    legacy_question = QuestEvaluationQuestion(
        title="第一章",
        question_type="选择",
        question_name="这是题目",
        options=["选项A", "选项B", "选项C", "选项D"],
        chunk_ids=["chunk-1"],
        studuent=[1],
        answer=[0],
        score=0,
    )

    assert legacy_question.student == [1]


def test_quest_service_treats_empty_choice_student_answer_as_unanswered():
    service = QuestService()
    question = QuestEvaluationQuestion(
        title="第一章",
        question_type="选择",
        question_name="这是题目",
        options=["选项A", "选项B", "选项C", "选项D"],
        chunk_ids=["chunk-1"],
        student=[],
        answer=[0],
        score=0,
    )

    payload = service._build_question_performance_payload(question, "选择")

    assert payload["correct_answer"] == "选项A"
    assert payload["student_answer"] == "未作答"
