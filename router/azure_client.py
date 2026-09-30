
from openai import OpenAI
from openai.types.responses import FunctionToolParam

from config.settings import AzureSettings
from mcp_server.schemas import ToolSpecification


def make_client(settings: AzureSettings) -> OpenAI:
    return OpenAI(
        base_url=settings.azure_base_url,
        api_key=settings.azure_api_key.get_secret_value(),
    )
    
def to_azure_tool_definition(spec: ToolSpecification) -> FunctionToolParam:
    return {
        "type": "function",
        "name": spec.name.value,
        "description": spec.description,
        "parameters": spec.args.model_json_schema(),
        "strict": False,
    }