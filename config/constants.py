from typing import Final


class ToolMessages:
    NO_MATCHES: Final[str] = "No matches found."
    MATCHES_TRUNCATED: Final[str] = (
        "[truncated: showing {shown} of {total} matches. Narrow the pattern or path.]"
    )
    LINES_TRUNCATED: Final[str] = (
        "[truncated: showing {shown} of {total} lines. Narrow the line range.]"
    )
    OUTPUT_OMITTED: Final[str] = "\n[... {omitted} characters omitted ...]\n"

    PATH_NOT_FOUND: Final[str] = (
        "The path {path} does not exist. Use glob or grep to search for the right path."
    )
    NOT_A_FILE: Final[str] = (
        "The path {path} is not a valid file. Use glob or grep to search for the right path."
    )
    BINARY_FILE: Final[str] = (
        "The file {path} is binary and cannot be read as text. "
        "Use run with a command like file or xxd to inspect it."
    )
    SANDBOX_FAILED: Final[str] = "The sandbox could not run the request: {error}"
    PATH_OUTSIDE_WORKSPACE: Final[str] = (
        "The path {path} is outside the project root {root}. "
        "Only paths inside the project root can be used."
    )
    INVALID_LINE_RANGE: Final[str] = (
        "Invalid line range: start_line must be at least 1 "
        "and end_line must be at least start_line."
    )
    INVALID_REGEX: Final[str] = "Invalid regex pattern: {error}"

    EDIT_SAME_STRING: Final[str] = (
        "old_string and new_string are the same. No changes made."
    )
    EDIT_EMPTY_OLD_STRING: Final[str] = "old_string cannot be empty."
    EDIT_NOT_FOUND: Final[str] = (
        "old_string was not found in {path}. Use read to copy the exact text."
    )
    EDIT_NOT_UNIQUE: Final[str] = (
        "old_string was found {count} times in {path}. "
        "Include more surrounding lines to make it unique."
    )
    DIFF_BEFORE_LABEL: Final[str] = "{path} (before)"
    DIFF_AFTER_LABEL: Final[str] = "{path} (after)"

    COMMAND_TIMEOUT: Final[str] = "Command timed out after {timeout} seconds."
    COMMAND_OUTPUT: Final[str] = (
        "exit code: {exit_code}\nstdout:\n{stdout}\nstderr:\n{stderr}"
    )


class ExecutorMessages:
    ERROR_PREFIX: Final[str] = "Error: "
    INVALID_TOOL_CALL: Final[str] = (
        "Invalid call to {tool}. The tool must be one of: {available}, "
        "and the arguments must be a JSON object."
    )
    TOOL_FAILED: Final[str] = "Tool {tool} failed with error: {error}"
    TOOL_BLOCKED: Final[str] = "Tool {tool} was blocked by policy rule: {rule}"


class FileListing:
    FALLBACK_IGNORED_DIRS: Final[frozenset[str]] = frozenset(
        {".git", ".venv", "__pycache__", "node_modules"}
    )
    GIT_LIST_FILES_COMMAND: Final[tuple[str, ...]] = (
        "git",
        "ls-files",
        "--cached",
        "--others",
        "--exclude-standard",
        "-z",
    )
    GIT_OUTPUT_SEPARATOR: Final[str] = "\0"


class EnvConfig:
    ENV_FILE: Final[str] = ".env"


class LogFields:
    TIMESTAMP: Final[str] = "timestamp"
    LEVEL: Final[str] = "level"
    LOGGER: Final[str] = "logger"
    MESSAGE: Final[str] = "message"
    EXCEPTION: Final[str] = "exception"


class LogMessages:
    TOOL_FAILED: Final[str] = "Tool failed with an unexpected exception."
    TOOL_BLOCKED: Final[str] = "Tool call blocked by policy rule."
    SECRET_MASKED: Final[str] = "Secrets masked in tool output."
    RUN_CRASHED: Final[str] = "Agent run crashed."
    TRACE_STARTED: Final[str] = "Trace file started."
    SANDBOX_CREATING: Final[str] = "Creating sandbox from the task image."
    SANDBOX_STOP_FAILED: Final[str] = "Could not stop the sandbox."
    TASK_STARTED: Final[str] = "SWE-bench task started."
    TASK_FAILED: Final[str] = "SWE-bench task crashed; recording an empty patch."
    TASK_FINISHED: Final[str] = "SWE-bench task finished."


class PolicyMessages:
    INVALID_RULE: Final[str] = (
        "Invalid policy rule {rule!r}. Rules look like tool(pattern), "
        "e.g. run(git push *)."
    )
    UNKNOWN_TOOL: Final[str] = (
        "Invalid policy rule {rule!r}: unknown tool {tool!r}. Known tools: {known}."
    )


class PolicyFileMessages:
    NOT_FOUND: Final[str] = "Policy file not found: {path}"
    INVALID: Final[str] = "Policy file {path} is invalid: {error}"


class PolicyFormat:
    # tool name, then the pattern inside one pair of brackets
    RULE_REGEX: Final[str] = r"(\w+)\((.*)\)"


class ProtectedPathRules:
    HARNESS: Final[str] = "protected path: harness code"
    PROTECTED_DIR: Final[str] = "protected path: {name} folder"


class CliMessages:
    DESCRIPTION: Final[str] = "A mini coding agent."
    PRINT_HELP: Final[str] = "Run one prompt, print the answer, and exit."
    STOPPED: Final[str] = "[stopped: {reason}]"
    SUMMARY: Final[str] = "[{tokens} tokens · ${cost:.4f}]"


class UiMessages:
    TITLE: Final[str] = "mclaude"
    INPUT_PLACEHOLDER: Final[str] = "Ask for a change, or type exit to quit"
    EXIT_COMMAND: Final[str] = "exit"
    TOOL_CALL: Final[str] = "⏺ {tool}  {arguments}"
    RESULT_TITLE: Final[str] = "result · {lines} lines"
    RESULT_CUT: Final[str] = "… {hidden} more lines"
    STOPPED: Final[str] = "Stopped: {reason}"
    STATUS: Final[str] = "{tokens:,} tokens · ${cost:.4f} · {folder}"
    RUN_CRASHED: Final[str] = "The run crashed: {error}. Details are in {log_file}."


class SecretNames:
    DAYTONA_API_KEY: Final[str] = "daytona_api_key"
    AZURE_API_KEY: Final[str] = "azure_api_key"


class SecretPatterns:
    PATTERNS: Final[dict[str, str]] = {
        "private_key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----",
        "openai_style_key": r"sk-[A-Za-z0-9_-]{20,}",
        "aws_access_key": r"AKIA[0-9A-Z]{16}",
    }
    REDACTED: Final[str] = "[REDACTED: {name}]"


class TraceFormat:
    RUNS_DIR_NAME: Final[str] = "runs"
    # runs started by hand (CLI or app); the eval harness names its own batches
    INTERACTIVE_BATCH: Final[str] = "interactive"
    FILE_SUFFIX: Final[str] = ".jsonl"
    RUN_ID_TIME_FORMAT: Final[str] = "%Y%m%dT%H%M%S%f"
    # grep prints "path:line: text"; the path is everything before ":<line>: "
    GREP_LINE_PATH_REGEX: Final[str] = r"^(.+?):\d+: "
    GIT_HEAD_COMMAND: Final[str] = "git rev-parse HEAD"
    GIT_TIMEOUT_SECONDS: Final[int] = 30


class RemoteCommands:
    """Shell commands the Daytona workspace runs inside the sandbox."""

    TEST: Final[str] = "test {flag} {path}"
    TEST_FILE_FLAG: Final[str] = "-f"
    TEST_EXISTS_FLAG: Final[str] = "-e"
    # tracked plus untracked-but-not-ignored files, relative to the repo root
    LIST_FILES: Final[str] = (
        "git ls-files --cached --others --exclude-standard --full-name -- {path}"
    )
    # -I skips binary files; --untracked also searches new files the agent made
    GREP: Final[str] = "git grep -n -I --untracked --full-name -P -e {regex} -- {path}"
    GREP_LINE_REGEX: Final[str] = r"^(.+?):(\d+):(.*)$"


class Prompts:
    SYSTEM: Final[str] = (
        "You are a coding agent working in a software repository. "
        "Use the tools to investigate and change the code; never guess at file "
        "contents. Search with grep and glob, read the relevant code, then make "
        "small, targeted edits. Paths are relative to the repository root. "
        "Before your final reply, run the relevant tests with run to check your "
        "change. Your final reply should briefly say what you changed and why."
    )
    SWE_TASK: Final[str] = (
        "Fix the following GitHub issue in this repository.\n\n"
        "<issue>\n{issue}\n</issue>\n\n"
        "Change only non-test source files; the fix is graded by hidden tests. "
        "Reproduce the problem first if you can, then make the smallest change "
        "that fixes it, and run the existing tests near the code you changed."
    )


class EvalMessages:
    DESCRIPTION: Final[str] = (
        "Run the agent on SWE-bench Lite tasks in Daytona sandboxes."
    )
    BATCH_HELP: Final[str] = (
        "Name for this batch; traces and predictions go to runs/<batch>/."
    )
    INSTANCE_HELP: Final[str] = (
        "A task to run, e.g. django__django-11099. Repeat for more."
    )
    LIMIT_HELP: Final[str] = "Run at most this many tasks."
    GIT_DIFF_COMMAND: Final[str] = "git diff"
    PATH_VARIABLE: Final[str] = "PATH"
