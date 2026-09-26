import subprocess
from pathlib import Path

FALLBACK_IGNORED_DIRS = {".git", ".venv", "__pycache__", "node_modules"}
GIT_LIST_FILES_COMMAND = [
    "git",
    "ls-files",
    "--cached",
    "--others",
    "--exclude-standard",
    "-z",
]


def list_project_files(root: Path) -> list[Path]:
    try:
        result = subprocess.run(
            GIT_LIST_FILES_COMMAND,
            cwd=root,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return _walk_files(root)

    if result.returncode != 0:
        return _walk_files(root)

    names = [name for name in result.stdout.split("\0") if name]
    files = [root / name for name in names]
    return [file for file in files if file.is_file()]


def _walk_files(root: Path) -> list[Path]:
    return [
        file
        for file in root.rglob("*")
        if file.is_file()
        and not any(part in FALLBACK_IGNORED_DIRS for part in file.parts)
    ]
