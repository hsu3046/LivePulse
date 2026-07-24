from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class EventCreate(BaseModel):
    title: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=300)

    @field_validator("title", "description", mode="before")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=300)

    @field_validator("title", "description", mode="before")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class QuestionCreate(BaseModel):
    text: str = Field(min_length=2, max_length=200)
    type: Literal["SINGLE", "RATING"] = "SINGLE"
    options: list[str] = Field(default_factory=list, max_length=10)
    chart_type: Literal["BAR", "PIE"] = "BAR"
    min_label: str = Field(default="매우 낮음", max_length=40)
    max_label: str = Field(default="매우 높음", max_length=40)

    @field_validator("text", "min_label", "max_label", mode="before")
    @classmethod
    def strip_fields(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @field_validator("options")
    @classmethod
    def normalize_options(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]

    @model_validator(mode="after")
    def validate_question(self) -> "QuestionCreate":
        if self.type == "SINGLE":
            if not 2 <= len(self.options) <= 10:
                raise ValueError("단일 선택 질문은 2~10개의 선택지가 필요합니다.")
            lowered = [option.casefold() for option in self.options]
            if len(set(lowered)) != len(lowered):
                raise ValueError("중복된 선택지는 사용할 수 없습니다.")
            if any(len(option) > 80 for option in self.options):
                raise ValueError("선택지는 80자 이하여야 합니다.")
        return self


class QuestionUpdate(QuestionCreate):
    pass


class ReorderQuestions(BaseModel):
    question_ids: list[str] = Field(min_length=1)


class JoinRequest(BaseModel):
    participant_session_id: str | None = None


class ResponseSubmit(BaseModel):
    participant_session_id: str = Field(min_length=8, max_length=80)
    option_id: str = Field(min_length=8, max_length=80)
    idempotency_key: str | None = Field(default=None, max_length=100)
