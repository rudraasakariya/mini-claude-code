from config.constants import SecretPatterns
from hooks.guardrails import Guardrails
from hooks.policy import Policy
from hooks.post_tool import post_tool

EMPTY_POLICY = Policy(deny={}, ask={})


def test_known_secret_is_masked():
    guardrails = Guardrails(
        policy=EMPTY_POLICY, secrets={"azure_api_key": "s3cr3t-value"}
    )
    result = post_tool("key=s3cr3t-value\n", guardrails)
    assert (
        result == "key=" + SecretPatterns.REDACTED.format(name="azure_api_key") + "\n"
    )


def test_key_shaped_text_is_masked():
    guardrails = Guardrails(policy=EMPTY_POLICY)
    key = "sk-" + "a" * 30
    result = post_tool(f"OPENAI_API_KEY={key}", guardrails)
    assert key not in result
    assert SecretPatterns.REDACTED.format(name="openai_style_key") in result


def test_output_without_secrets_is_unchanged():
    guardrails = Guardrails(
        policy=EMPTY_POLICY, secrets={"azure_api_key": "s3cr3t-value"}
    )
    assert post_tool("exit code: 0\n", guardrails) == "exit code: 0\n"
