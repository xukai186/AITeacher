from pydantic import BaseModel, Field


class ChatPostRequest(BaseModel):
    agent_type: str = Field(pattern="^(planner|subject)$")
    subject_code: str | None = Field(default=None, max_length=40)
    message: str = Field(min_length=1, max_length=8000)


class ChatPostResponse(BaseModel):
    session_id: str
    assistant_message: str
    tools_used: list[str] = []
