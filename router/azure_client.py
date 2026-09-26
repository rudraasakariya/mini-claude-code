from typing import Any

from openai import OpenAI

from config.settings import AzureSettings
from mcp_server.schemas import ToolSpec

def make_client(settings: AzureSettings) -> OpenAI:
    return OpenAI(
        base_url=settings.azure_base_url,
        api_key=settings.azure_api_key.get_secret_value(),
    )
    
def to_tool_definition(spec: ToolSpec) -> dict[str , Any]:
    return {
        "type": "function",
        "name": spec.name.value,
        "description": spec.description,
        "parameters": spec.args.model_json_schema(),
    }