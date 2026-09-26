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
    TOOL_NOT_AVAILABLE: Final[str] = "Tool {tool} is not available yet."


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
