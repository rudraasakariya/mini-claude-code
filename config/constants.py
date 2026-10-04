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
