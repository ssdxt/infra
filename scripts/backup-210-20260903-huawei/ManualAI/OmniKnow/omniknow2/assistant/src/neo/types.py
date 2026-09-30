from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.prompts.planner_model import Step, StepType


class NeoPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")

    locale: str = Field(
        default="",
        description="e.g. 'en-US' or 'zh-CN', based on the user's language",
    )
    thought: str = Field(
        default="",
        description="Brief reasoning for selecting the next step or ending now",
    )
    title: str = Field(default="", description="Current task title")
    direct_answer: str = Field(
        default="",
        description="Final answer when the scheduler can answer directly from supplied context",
    )
    next_step: Step | None = Field(
        default=None,
        description="Single executable next step. Null means stop scheduling and hand off to summary.",
    )


class SummaryClaim(BaseModel):
    text: str = Field(..., description="One user-visible claim for the final answer")
    citation_ids: list[str] = Field(
        default_factory=list,
        description="Resource IDs like S1, S2 that support this claim",
    )


class SummaryDraft(BaseModel):
    claims: list[SummaryClaim] = Field(
        default_factory=list,
        description="All final answer claims. Every claim must include at least one resource id in citation_ids.",
    )


class FactCheckItem(BaseModel):
    claim_index: int = Field(..., description="0-based index of the checked claim")
    verdict: Literal["supported", "partially_supported", "unsupported"] = Field(
        ...,
        description="Whether the claim is supported by the available findings and cited resources",
    )
    reason: str = Field(default="", description="Short explanation for the verdict")
    revised_text: str = Field(
        default="",
        description="A tighter, evidence-aligned rewrite of the claim. Empty if the claim should be dropped.",
    )


class FactCheckReview(BaseModel):
    items: list[FactCheckItem] = Field(
        default_factory=list,
        description="Fact-check verdicts for each summary claim",
    )
    grounded_ratio: float = Field(
        default=0.0,
        description="Estimated share of claims grounded in retrieved evidence",
    )
    free_generation_ratio: float = Field(
        default=0.0,
        description="Estimated share of claims that may rely on model free generation",
    )


__all__ = [
    "FactCheckItem",
    "FactCheckReview",
    "NeoPlan",
    "Step",
    "StepType",
    "SummaryClaim",
    "SummaryDraft",
]
