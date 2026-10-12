"""Convert ordinary Markdown tables into readable lists without discarding values."""
from __future__ import annotations

import re


def _cells(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith(r"\|"):
        line = line[:-1]
    return [part.strip().replace(r"\|", "|") for part in re.split(r"(?<!\\)\|", line)]


def _separator(line: str, width: int) -> bool:
    cells = _cells(line)
    return (
        len(cells) == width
        and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)
    )


def _fence(line: str) -> str | None:
    match = re.match(r"^\s{0,3}((?:\x60){3,}|~{3,})", line)
    return match.group(1) if match else None


def _convert(text: str, *, convert: bool) -> tuple[str, bool]:
    lines = text.splitlines(keepends=True)
    output: list[str] = []
    i = 0
    fence = ""
    found = False

    while i < len(lines):
        line = lines[i]
        opener = _fence(line)
        if opener:
            if not fence:
                fence = opener
            elif opener[0] == fence[0] and len(opener) >= len(fence):
                fence = ""
            output.append(line)
            i += 1
            continue

        if fence:
            output.append(line)
            i += 1
            continue

        if i + 2 < len(lines) and "|" in line:
            headers = _cells(line)
            if len(headers) >= 2 and _separator(lines[i + 1], len(headers)):
                rows = []
                j = i + 2
                valid = True
                while j < len(lines) and "|" in lines[j] and lines[j].strip():
                    cells = _cells(lines[j])
                    if len(cells) != len(headers):
                        valid = False
                        break
                    rows.append(cells)
                    j += 1
                if rows and valid:
                    found = True
                    if convert:
                        for row in rows:
                            details = [
                                f"**{head}:** {cell}" if head else cell
                                for head, cell in zip(headers, row)
                            ]
                            output.append("- " + "; ".join(details) + "\n")
                        output.append("\n")
                    else:
                        output.extend(lines[i:j])
                    i = j
                    continue

        output.append(line)
        i += 1

    result = "".join(output)
    if re.search(r"<table(?:\s|>)", result, flags=re.IGNORECASE):
        found = True
    return result, found


def format_article(text: str, *, allow_tables: bool = False) -> tuple[str, bool]:
    """Return text and whether unsupported tables remain in the output."""
    if allow_tables:
        return text, False
    converted, _ = _convert(text, convert=True)
    _, remaining = _convert(converted, convert=False)
    return converted, remaining
