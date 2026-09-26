from dataclasses import dataclass

from pydantic import BaseModel

from agent.state import ToolName


@dataclass(frozen=True)
class ToolSpec:
    name: ToolName
    description: str
    args: type[BaseModel]
