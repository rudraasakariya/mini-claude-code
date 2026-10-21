import posixpath
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol

from daytona import DaytonaError, DaytonaNotFoundError, DaytonaTimeoutError, Sandbox

from config.constants import RemoteCommands, ToolMessages
from mcp_server.errors import ToolError
from mcp_server.project_files import list_project_files


@dataclass(frozen=True)
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class GrepMatch:
    path: str  # relative to the workspace root
    line_number: int
    line: str


class Workspace(Protocol):
    """
    The project the tools work on. Every path in and out is relative to the
    root, so the tools never know whether the files are local or in a sandbox.
    """

    @property
    def root(self) -> Path: ...

    def is_file(self, path: str) -> bool: ...

    def exists(self, path: str) -> bool: ...

    def read_text(self, path: str) -> str: ...

    def write_text(self, path: str, text: str) -> None: ...

    def list_files(self, path: str) -> list[str]: ...

    def grep(self, regex: str, path: str) -> list[GrepMatch]: ...

    def run(self, command: str, timeout: int) -> CommandResult: ...


def resolve_in_workspace(path: str, root_path: Path) -> Path:
    """
    Resolve a path the model gave against the workspace root, and refuse it
    if it ends up outside the root (via ../, an absolute path, or a symlink).
    """
    absolute_path = (root_path / path).resolve()
    if not absolute_path.is_relative_to(root_path):
        raise ToolError(
            ToolMessages.PATH_OUTSIDE_WORKSPACE.format(path=path, root=root_path)
        )
    return absolute_path


class LocalWorkspace:
    """Files on this machine, under root."""

    def __init__(self, root: Path):
        self._root = root.resolve()

    @property
    def root(self) -> Path:
        return self._root

    def _resolve(self, path: str) -> Path:
        return resolve_in_workspace(path, self._root)

    def _relative(self, file: Path) -> str:
        return str(file.relative_to(self._root))

    def is_file(self, path: str) -> bool:
        return self._resolve(path).is_file()

    def exists(self, path: str) -> bool:
        return self._resolve(path).exists()

    def read_text(self, path: str) -> str:
        return self._resolve(path).read_text()

    def write_text(self, path: str, text: str) -> None:
        self._resolve(path).write_text(text)

    def list_files(self, path: str) -> list[str]:
        start = self._resolve(path)
        files = [start] if start.is_file() else list_project_files(start)
        return [self._relative(file) for file in files]

    def grep(self, regex: str, path: str) -> list[GrepMatch]:
        compiled = re.compile(regex)
        matches: list[GrepMatch] = []
        for relative in self.list_files(path):
            try:
                text = (self._root / relative).read_text()
            except UnicodeDecodeError:
                continue  # binary file, nothing to search
            for number, line in enumerate(text.splitlines(), start=1):
                if compiled.search(line):
                    matches.append(GrepMatch(relative, number, line))
        return matches

    def run(self, command: str, timeout: int) -> CommandResult:
        try:
            result = subprocess.run(
                command,
                cwd=self._root,
                shell=True,
                capture_output=True,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            raise ToolError(ToolMessages.COMMAND_TIMEOUT.format(timeout=timeout)) from e
        return CommandResult(result.returncode, result.stdout, result.stderr)


class DaytonaWorkspace:
    """
    Files inside a Daytona sandbox. The sandbox is the security wall, so paths
    are only normalized here; symlinks inside it can't reach this machine.
    """

    def __init__(
        self,
        sandbox: Sandbox,
        root: Path,
        command_timeout: int,
        env: dict[str, str] | None = None,
    ):
        self._sandbox = sandbox
        self._env = env or {}
        self._root = root
        self._command_timeout = command_timeout  # for the harness's own commands

    @property
    def root(self) -> Path:
        return self._root

    def _resolve(self, path: str) -> str:
        absolute = posixpath.normpath(posixpath.join(str(self._root), path))
        if not PurePosixPath(absolute).is_relative_to(PurePosixPath(self._root)):
            raise ToolError(
                ToolMessages.PATH_OUTSIDE_WORKSPACE.format(path=path, root=self._root)
            )
        return absolute

    def _test(self, flag: str, path: str) -> bool:
        command = RemoteCommands.TEST.format(
            flag=flag, path=shlex.quote(self._resolve(path))
        )
        return self.run(command, self._command_timeout).exit_code == 0

    def is_file(self, path: str) -> bool:
        return self._test(RemoteCommands.TEST_FILE_FLAG, path)

    def exists(self, path: str) -> bool:
        return self._test(RemoteCommands.TEST_EXISTS_FLAG, path)

    def read_text(self, path: str) -> str:
        try:
            content = self._sandbox.fs.download_file(self._resolve(path))
        except DaytonaNotFoundError as e:
            raise ToolError(ToolMessages.NOT_A_FILE.format(path=path)) from e
        # raises UnicodeDecodeError for binary files, same as Path.read_text
        return (content or b"").decode()

    def write_text(self, path: str, text: str) -> None:
        self._sandbox.fs.upload_file(text.encode(), self._resolve(path))

    def list_files(self, path: str) -> list[str]:
        start = self._resolve(path)
        if self.is_file(path):
            return [posixpath.relpath(start, self._root)]
        command = RemoteCommands.LIST_FILES.format(path=shlex.quote(start))
        result = self.run(command, self._command_timeout)
        return [line for line in result.stdout.splitlines() if line]

    def grep(self, regex: str, path: str) -> list[GrepMatch]:
        command = RemoteCommands.GREP.format(
            regex=shlex.quote(regex), path=shlex.quote(self._resolve(path))
        )
        result = self.run(command, self._command_timeout)
        matches: list[GrepMatch] = []
        for line in result.stdout.splitlines():
            found = re.match(RemoteCommands.GREP_LINE_REGEX, line)
            if found:
                file, number, text = found.groups()
                matches.append(GrepMatch(file, int(number), text))
        return matches

    def run(self, command: str, timeout: int) -> CommandResult:
        try:
            response = self._sandbox.process.exec(
                command, cwd=str(self._root), env=self._env, timeout=timeout
            )
        except DaytonaTimeoutError as e:
            raise ToolError(ToolMessages.COMMAND_TIMEOUT.format(timeout=timeout)) from e
        except DaytonaError as e:
            raise ToolError(ToolMessages.SANDBOX_FAILED.format(error=e)) from e
        # the sandbox returns stdout and stderr as one stream
        return CommandResult(int(response.exit_code), response.result, "")
