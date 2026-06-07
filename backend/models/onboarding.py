from pydantic import BaseModel, Field, field_validator


class CreateCaseRequest(BaseModel):
    employee_name:  str = Field(..., min_length=1, max_length=200)
    employee_email: str = Field(..., min_length=3, max_length=200)
    employee_id:    str = Field(default="", max_length=100)
    department:     str = Field(default="", max_length=200)
    role:           str = Field(default="", max_length=200)
    manager_name:   str = Field(default="", max_length=200)
    start_date:     str = Field(default="", max_length=50)

    @field_validator("employee_name", "employee_email")
    @classmethod
    def strip_str(cls, v: str) -> str:
        return v.strip()


class CompleteItemRequest(BaseModel):
    stage_id: str = Field(..., min_length=1, max_length=100)
    item_id:  str = Field(..., min_length=1, max_length=100)


class EscalateRequest(BaseModel):
    reason:       str = Field(..., min_length=1, max_length=1000)
    escalated_by: str = Field(default="employee", max_length=50)
