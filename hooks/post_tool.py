import logging
import re

from config.constants import LogMessages, SecretPatterns
from hooks.guardrails import Guardrails

logger = logging.getLogger(__name__)


def post_tool(observation: str, guardrails: Guardrails) -> str:
    """Return the tool output the model may see, with secrets hidden."""
    masked: list[str] = []

    # known values first: exact matches, so no false alarms
    for name, value in guardrails.secrets.items():
        if value and value in observation:
            observation = observation.replace(
                value, SecretPatterns.REDACTED.format(name=name)
            )
            masked.append(name)

    # then patterns, for secrets the harness doesn't know about
    for name, pattern in SecretPatterns.PATTERNS.items():
        observation, count = re.subn(
            pattern, SecretPatterns.REDACTED.format(name=name), observation
        )
        if count:
            masked.append(name)

    if masked:
        # log which kinds were hidden, never the values themselves
        logger.warning(LogMessages.SECRET_MASKED, extra={"secrets": masked})
    return observation
