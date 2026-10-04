from dataclasses import dataclass, field

from hooks.policy import Policy


@dataclass(frozen=True)
class Guardrails:
    """Everything the hooks need at run time, built once at startup."""

    policy: Policy
    # secret name -> value; post-tool hooks hide these values from the model
    secrets: dict[str, str] = field(default_factory=dict)
