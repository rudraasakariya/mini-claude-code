import subprocess
from pathlib import Path

from config.constants import FileListing


def list_project_files(root: Path) -> list[Path]:
    try:
        result = subprocess.run(
            FileListing.GIT_LIST_FILES_COMMAND,
            cwd=root,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return _walk_files(root)

    if result.returncode != 0:
        return _walk_files(root)

    names = [
        name for name in result.stdout.split(FileListing.GIT_OUTPUT_SEPARATOR) if name
    ]
    files = [root / name for name in names]
    return [file for file in files if file.is_file()]


def _walk_files(root: Path) -> list[Path]:
    return [
        file
        for file in root.rglob("*")
        if file.is_file()
        and not any(part in FileListing.FALLBACK_IGNORED_DIRS for part in file.parts)
    ]
