from openai import OpenAI, Timeout
from openai.types.responses import FunctionToolParam

from config.settings import AzureSettings, OpenAISettings
from mcp_server.schemas import ToolSpecification


def make_client(settings: AzureSettings, openai_settings: OpenAISettings) -> OpenAI:
    return OpenAI(
        base_url=settings.azure_base_url,
        api_key=settings.azure_api_key.get_secret_value(),
        max_retries=openai_settings.max_retries,
        timeout=Timeout(
            openai_settings.timeout_seconds,
            connect=openai_settings.connect_timeout_seconds,
        ),
    )


def to_azure_tool_definition(spec: ToolSpecification) -> FunctionToolParam:
    return {
        "type": "function",
        "name": spec.name.value,
        "description": spec.description,
        "parameters": spec.args.model_json_schema(),
        "strict": False,
    }
