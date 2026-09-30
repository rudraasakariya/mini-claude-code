from dataclasses import dataclass

from pydantic import BaseModel

from agent.state import ToolName


@dataclass(frozen=True)
class ToolSpecification:
    name: ToolName
    description: str
    args: type[BaseModel]
