from typing import Literal

from pydantic import BaseModel

from .action import (
    GUIAction,
    ApiAction,
    CodeAction,
    MessageAction,
    TextObservation,
    ImageObservation,
)


class Trajectory(BaseModel):
    task_id: str
    example_id: str | None = None
    type: Literal["grounding", "end2end"]
    content: list[GUIAction | ApiAction | CodeAction | MessageAction | TextObservation | ImageObservation]

