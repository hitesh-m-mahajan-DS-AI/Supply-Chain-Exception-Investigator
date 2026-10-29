"""Strict request/output contracts; user requests cannot supply endpoints or SQL."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    passage_id: str = Field(min_length=3, max_length=50)
    quote: str = Field(min_length=12, max_length=450)


class Draft(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    status: Literal["supported", "insufficient", "conflict"]
    evidence: list[Evidence] = Field(max_length=3)

    @model_validator(mode="after")
    def evidence_matches_status(self):
        if self.status == "insufficient" and self.evidence:
            raise ValueError("Insufficient answers must have no selected quotes.")
        if self.status == "supported" and not self.evidence:
            raise ValueError("Supported answers need a quote.")
        if self.status == "conflict" and len({e.passage_id for e in self.evidence}) < 2:
            raise ValueError("Conflicts need at least two distinct passages.")
        return self


class InvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    case_id: str = Field(pattern=r"^EX-[0-9]{4}$")
    question: str = Field(min_length=5, max_length=400)
    mode: Literal["local_ai", "search_only"] = "local_ai"
    model: Literal["qwen2.5:1.5b", "qwen2.5:0.5b"] = "qwen2.5:1.5b"
    prompt_version: Literal["v1", "v2"] = "v2"


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    disposition: Literal["reviewed", "needs_follow_up"]
    note: str = Field(min_length=1, max_length=1200)
