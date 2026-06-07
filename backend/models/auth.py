from pydantic import BaseModel, Field


class SignupRequest(BaseModel):
    email:     str = Field(..., min_length=5,  max_length=200)
    password:  str = Field(..., min_length=8,  max_length=200)
    full_name: str = Field(..., min_length=1,  max_length=200)


class LoginRequest(BaseModel):
    email:    str = Field(..., min_length=5,  max_length=200)
    password: str = Field(..., min_length=1,  max_length=200)
