import json
import logging

from openai import OpenAI
from textual import work
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Collapsible, Input, LoadingIndicator, Markdown, Static

from agent.events import (
    AgentEvent,
    AssistantText,
    ModelCallStarted,
    RunFinished,
    ToolCallFinished,
    ToolCallStarted,
    fan_out,
)
from agent.loop import run_agent_loop
from agent.state import (
    Action,
    InvalidToolCall,
    LoopState,
    MessagePhase,
    State,
    UserTurn,
)
from config.constants import LogMessages, UiMessages
from config.settings import RunConfig, UiSettings
from hooks.guardrails import Guardrails
from mcp_server.workspace import LocalWorkspace
from trace_store.store import open_trace

logger = logging.getLogger(__name__)


class AgentApp(App[None]):
    """Interactive mode: a chat view of the agent's run, with an input box."""

    CSS = """
    #chat { height: 1fr; padding: 0 1; }
    .user { margin: 1 0 0 0; color: $text; text-style: bold; background: $boost; }
    .commentary { color: $text-muted; }
    .tool-call { color: $warning; }
    .stopped { color: $error; }
    Collapsible { margin: 0 0 0 2; }
    LoadingIndicator { height: 1; }
    #status { height: 1; padding: 0 1; background: $panel; color: $text-muted; }
    """

    def __init__(
        self,
        client: OpenAI,
        model: str,
        config: RunConfig,
        guardrails: Guardrails,
        ui_settings: UiSettings,
    ) -> None:
        super().__init__()
        self.client = client
        self.model = model
        self.config = config
        self.guardrails = guardrails
        self.ui_settings = ui_settings
        self.state = State()  # one conversation for the whole session

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="chat")
        yield LoadingIndicator(id="spinner")
        yield Input(placeholder=UiMessages.INPUT_PLACEHOLDER, id="prompt")
        yield Static(self.status_text(), id="status")

    def on_mount(self) -> None:
        self.title = UiMessages.TITLE
        self.query_one("#spinner").display = False
        self.query_one("#prompt", Input).focus()

    # ---- input -----------------------------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        prompt = event.value.strip()
        event.input.value = ""
        if not prompt:
            return
        if prompt == UiMessages.EXIT_COMMAND:
            self.exit()
            return
        self.add_to_chat(Static(f"> {prompt}", classes="user", markup=False))
        self.set_busy(True)
        self.run_agent(prompt)

    @work(thread=True, exclusive=True)
    def run_agent(self, prompt: str) -> None:
        """Runs in a background thread so the screen stays responsive."""
        self.state.conversation.append(UserTurn(prompt))
        try:
            # each prompt is its own run, so it gets its own trace file
            workspace = LocalWorkspace(self.config.workspace.root_path)
            recorder = open_trace(self.config, workspace, self.model, task=prompt)
            run_agent_loop(
                self.client,
                self.model,
                self.state,
                self.config,
                self.guardrails,
                workspace,
                on_event=fan_out(
                    # events come from this thread; hand each one to the UI thread
                    lambda event: self.call_from_thread(self.show_event, event),
                    recorder,
                ),
            )
        except Exception as error:
            logger.exception(LogMessages.RUN_CRASHED)
            self.call_from_thread(self.show_crash, error)
        finally:
            self.call_from_thread(self.set_busy, False)

    # ---- events → widgets -----------------------------------------------

    def show_event(self, event: AgentEvent) -> None:
        match event:
            case ModelCallStarted():
                self.query_one("#spinner").display = True
            case ToolCallStarted(action=action, preamble=preamble):
                if preamble is not None:
                    self.add_to_chat(Markdown(preamble.text, classes="commentary"))
                self.add_to_chat(
                    Static(
                        self.tool_call_text(action), classes="tool-call", markup=False
                    )
                )
            case ToolCallFinished(observation=observation):
                self.add_to_chat(self.result_widget(observation))
            case AssistantText(message=message):
                is_final = message.phase is MessagePhase.FINAL_ANSWER
                self.add_to_chat(
                    Markdown(message.text, classes="" if is_final else "commentary")
                )
            case RunFinished(stop_reason=stop_reason):
                if stop_reason is not LoopState.FINAL_ANSWER_GIVEN:
                    text = UiMessages.STOPPED.format(reason=stop_reason.value)
                    self.add_to_chat(Static(text, classes="stopped", markup=False))
                self.query_one("#status", Static).update(self.status_text())

    def show_crash(self, error: Exception) -> None:
        text = UiMessages.RUN_CRASHED.format(
            error=type(error).__name__, log_file=self.ui_settings.log_file
        )
        self.add_to_chat(Static(text, classes="stopped", markup=False))

    # ---- helpers ---------------------------------------------------------

    def tool_call_text(self, action: Action | InvalidToolCall) -> str:
        match action:
            case Action(tool=tool, arguments=arguments):
                name, shown = tool.value, json.dumps(arguments)
            case InvalidToolCall(name=raw_name, arguments=raw_arguments):
                name, shown = raw_name, raw_arguments
        limit = self.ui_settings.max_argument_chars
        if len(shown) > limit:
            shown = shown[:limit] + "…"
        return UiMessages.TOOL_CALL.format(tool=name, arguments=shown)

    def result_widget(self, observation: str) -> Collapsible:
        lines = observation.splitlines()
        limit = self.ui_settings.max_result_lines
        shown = "\n".join(lines[:limit])
        if len(lines) > limit:
            shown += "\n" + UiMessages.RESULT_CUT.format(hidden=len(lines) - limit)
        return Collapsible(
            Static(shown, markup=False),
            title=UiMessages.RESULT_TITLE.format(lines=len(lines)),
            collapsed=True,
        )

    def add_to_chat(self, widget: Static | Markdown | Collapsible) -> None:
        chat = self.query_one("#chat", VerticalScroll)
        chat.mount(widget)
        chat.scroll_end(animate=False)

    def set_busy(self, busy: bool) -> None:
        self.query_one("#spinner").display = busy
        prompt = self.query_one("#prompt", Input)
        prompt.disabled = busy
        if not busy:
            prompt.focus()

    def status_text(self) -> str:
        return UiMessages.STATUS.format(
            tokens=self.state.token_count,
            cost=self.state.spend,
            folder=self.config.workspace.root_path.name,
        )
