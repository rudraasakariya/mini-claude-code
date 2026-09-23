import re
from pathlib import Path

IGNORED_DIRS = {".git", "__pycache__", "node_modules"}
NO_MATCHES_MESSAGE = "No matches found."
TRUNCATION_NOTICE = (
    "[truncated: showing {shown} of {total} matches. "
    "Narrow the pattern, path or include filter.]"
)


def grep(
    pattern: str,
    path: str = ".",
    include: str | None = None,
    *,
    max_results: int,
) -> str:
    try:
        regex = re.compile(pattern)
    except re.error as e:
        raise ValueError(f"Invalid regex pattern: {e}") from e

    root = Path(path)
    if not root.exists():
        raise FileNotFoundError(f"The path {path} does not exist.")

    files = [root] if root.is_file() else root.rglob(include or "*")

    matches: list[str] = []
    for file in files:
        if not file.is_file():
            continue
        if any(part in IGNORED_DIRS for part in file.parts):
            continue
        try:
            text = file.read_text()
        except UnicodeDecodeError:
            continue  # binary file, nothing to search
        for number, line in enumerate(text.splitlines(), start=1):
            if regex.search(line):
                matches.append(f"{file}:{number}: {line}")

    if not matches:
        return NO_MATCHES_MESSAGE

    shown = matches[:max_results]
    if len(matches) > max_results:
        shown.append(TRUNCATION_NOTICE.format(shown=max_results, total=len(matches)))
    return "\n".join(shown)
