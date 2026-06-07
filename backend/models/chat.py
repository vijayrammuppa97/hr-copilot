from typing import Literal
from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    message:        str       = Field(..., min_length=1, max_length=2000)
    conversationId: str       = Field(..., min_length=1, max_length=100)
    caseId:         str | None = Field(default=None, max_length=100)
    userId:         str | None = Field(default=None, max_length=100)

    @field_validator("message")
    @classmethod
    def strip_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message must not be blank")
        return v

    @field_validator("conversationId")
    @classmethod
    def strip_cid(cls, v: str) -> str:
        return v.strip()


class FeedbackRequest(BaseModel):
    messageId:      str = Field(..., min_length=1, max_length=100)
    conversationId: str = Field(..., min_length=1, max_length=100)
    feedback:       Literal["helpful", "not_helpful"]


class RegisterUserRequest(BaseModel):
    user_id:         str   | None = None
    username:        str   | None = None
    tenure_years:    float | None = None
    employment_type: str   | None = Field(default=None, max_length=50)
    department:      str   | None = Field(default=None, max_length=100)
    role:            str   | None = Field(default=None, max_length=100)


class UpdateProfileRequest(BaseModel):
    tenure_years:    float | None = None
    employment_type: str   | None = Field(default=None, max_length=50)
    department:      str   | None = Field(default=None, max_length=100)
    role:            str   | None = Field(default=None, max_length=100)
