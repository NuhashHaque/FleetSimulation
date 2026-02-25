from typing import Literal

from pydantic import BaseModel, Field


class CommandRequest(BaseModel):
    bus_id: str = Field(pattern=r"^BUS_[0-9]{2}$")
    action: Literal["START", "PAUSE", "STOP", "RESTART"]
    user_id: str = Field(min_length=1, max_length=128)
    trace_id: str | None = None
    command_id: str | None = None


class CommandAcceptedResponse(BaseModel):
    accepted: bool
    command_id: str
    trace_id: str
    bus_id: str
    action: str
    topic: str
