from openai import OpenAI

from config.settings import AzureSettings


def make_client(settings: AzureSettings) -> OpenAI:
    return OpenAI(
        base_url=settings.azure_base_url,
        api_key=settings.azure_api_key.get_secret_value(),
    )