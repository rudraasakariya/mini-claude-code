from pathlib import Path

def read_file(file_path: str, start_line: int, end_line: int) -> str:
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"The file {file_path} does not exist.")
    
    if start_line < 1 or end_line < start_line:
        raise ValueError("Invalid line range specified.")
    
    lines = path.read_text().splitlines()[start_line - 1:end_line]
    numbered = [f"{number}: {line}" for number, line in enumerate(lines, start=start_line)]
    return "\n".join(numbered)