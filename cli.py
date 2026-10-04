import argparse

from openai import OpenAI

from agent.loop import run_agent_loop
from agent.state import LoopState, State, TextTurn, UserTurn
from config.constants import CliMessages
from config.logging_setup import configure_logging
from config.settings import (
    AzureSettings,
    LoggingSettings,
    OpenAISettings,
    RunConfig,
    UiSettings,
)
from hooks.policy import Policy, load_policy
from router.azure_client import make_client
from ui.app import AgentApp


def run_prompt(
    prompt: str,
    client: OpenAI,
    model: str,
    state: State,
    config: RunConfig,
    policy: Policy,
) -> None:
    """Add the user's prompt to the history, run the agent, and print the result."""
    state.conversation.append(UserTurn(prompt))
    run_agent_loop(client, model, state, config, policy)

    last_turn = state.conversation[-1]
    if state.stop_reason is LoopState.FINAL_ANSWER_GIVEN and isinstance(
        last_turn, TextTurn
    ):
        print(last_turn.text)
    elif state.stop_reason is not None:
        print(CliMessages.STOPPED.format(reason=state.stop_reason.value))
    # tokens and cost are totals for the whole session, not just this prompt
    print(CliMessages.SUMMARY.format(tokens=state.token_count, cost=state.spend))


def main() -> None:
    parser = argparse.ArgumentParser(description=CliMessages.DESCRIPTION)
    parser.add_argument("-p", "--print", dest="prompt", help=CliMessages.PRINT_HELP)
    args = parser.parse_args()

    interactive = args.prompt is None
    ui_settings = UiSettings()
    # 1. logs: stderr in print mode; a file in the app so they don't draw over it
    log_file = ui_settings.log_file if interactive else None
    configure_logging(LoggingSettings(log_file=log_file))
    config = RunConfig()  # 2. all settings groups, defaults
    policy = load_policy(config.policy)  # 3. fails loudly if policy.json is broken
    # 4. pydantic-settings fills the fields from .env; type checkers can't see that
    azure = AzureSettings()  # type: ignore[call-arg]
    client = make_client(azure, OpenAISettings())

    if interactive:
        AgentApp(client, azure.azure_deployment, config, policy, ui_settings).run()
        return

    # print mode: one prompt, then exit
    run_prompt(args.prompt, client, azure.azure_deployment, State(), config, policy)


if __name__ == "__main__":
    main()
