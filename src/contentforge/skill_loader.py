"""Load user-owned editorial skill files in full, without LLM summaries.

Skill assets stay outside the public Git repository. Each stage receives original
files verbatim; Python never condenses or rewrites their contents.
"""
from __future__ import annotations

import hashlib
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile

from .terminal_settings import HOME

SKILL_NAME = "nikitina-text"
SKILL_DIRECTORY = HOME / "skills" / SKILL_NAME
REFERENCE_FILES = (
    "references/core-rules.md",
    "references/headlines-and-openings.md",
    "references/structure-and-clarity.md",
    "references/evidence-and-expertise.md",
    "references/storytelling-and-voice.md",
    "references/practical-texts-and-ethics.md",
    "references/editing-checklist.md",
)
REQUIRED = ("SKILL.md", *REFERENCE_FILES)
OPTIONAL = ("source-map.md",)
ALLOWED = frozenset((*REQUIRED, *OPTIONAL))
MAX_FILE_BYTES = 300_000
MAX_TOTAL_BYTES = 900_000

STAGE_FILES = {
    "outline": (
        "references/headlines-and-openings.md",
        "references/structure-and-clarity.md",
    ),
    # Full seven references, NOT excerpts or Python/LLM summaries.
    "writer": REFERENCE_FILES,
    "editor": REFERENCE_FILES,
    "quality": (
        "references/editing-checklist.md",
        "references/practical-texts-and-ethics.md",
    ),
}


@dataclass(frozen=True)
class SkillBundle:
    files: dict[str, str]
    digest: str

    @property
    def size_chars(self) -> int:
        return sum(len(s) for s in self.files.values())

    def context_for(self, agent: str) -> str:
        selected = STAGE_FILES.get(agent, ())
        if not selected:
            return ""
        chunks = [
            "ПОДКЛЮЧЁННЫЙ ПОЛНЫЙ НАВЫК nikitina-text. Ниже оригинальные файлы, "
            "а не сокращение. Соблюдай их принципы, не нарушая форматы "
            "входа/выхода агента, фактическую точность и отдельные "
            "ограничения редакционного профиля Дзена."
        ]
        for name in ("SKILL.md", *selected):
            chunks.append(f"\n\n===== НАВЫК / {name} =====\n{self.files[name]}")
        return "".join(chunks)


def read_skill(directory: Path = SKILL_DIRECTORY) -> SkillBundle:
    """Read and validate all original files, including references not used by every stage."""
    files = {}
    total = 0
    digest = hashlib.sha256()
    for name in REQUIRED:
        path = directory / name
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Отсутствует файл навыка: {path}")
        binary = path.read_bytes()
        if not binary or len(binary) > MAX_FILE_BYTES:
            raise ValueError(f"Недопустимый размер файла навыка: {name}")
        total += len(binary)
        if total > MAX_TOTAL_BYTES:
            raise ValueError("Общий размер навыка превышает безопасный предел.")
        try:
            content = binary.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(f"Файл навыка не в UTF-8: {name}") from error
        files[name] = content
        digest.update(name.encode("utf-8") + b"\0" + binary + b"\0")
    if "nikitina-text" not in files["SKILL.md"].lower():
        raise ValueError("ZIP содержит другой навык, ожидался nikitina-text.")
    return SkillBundle(files=files, digest=digest.hexdigest())


def install_zip(archive: Path, destination: Path = SKILL_DIRECTORY) -> SkillBundle:
    """Install one skill package. No extractall; unsafe ZIP paths are rejected."""
    archive = Path(archive).expanduser()
    if not archive.is_file():
        raise ValueError(f"ZIP не найден: {archive}")
    extracted: dict[str, bytes] = {}
    try:
        with ZipFile(archive) as bundle:
            total = 0
            for item in bundle.infolist():
                if item.is_dir():
                    continue
                filename = item.filename.replace("\\", "/")
                parts = filename.split("/")
                if len(parts) == 2 and parts[0] == SKILL_NAME:
                    name = parts[1]
                elif len(parts) == 3 and parts[0] == SKILL_NAME:
                    name = "/".join(parts[1:])
                elif len(parts) in (1, 2):
                    name = filename
                else:
                    raise ValueError("В ZIP неожиданная структура папок.")
                if name not in ALLOWED:
                    raise ValueError(f"Лишний или опасный файл в ZIP: {filename}")
                if name in extracted:
                    raise ValueError(f"Повторяющийся файл ZIP: {name}")
                if (item.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("Символические ссылки в ZIP запрещены.")
                if item.file_size <= 0 or item.file_size > MAX_FILE_BYTES:
                    raise ValueError(f"Недопустимый размер в ZIP: {name}")
                total += item.file_size
                if total > MAX_TOTAL_BYTES:
                    raise ValueError("Навык слишком большой.")
                payload = bundle.read(item)
                if len(payload) != item.file_size:
                    raise ValueError(f"ZIP повреждён: {name}")
                extracted[name] = payload
    except (zipfile.BadZipFile, RuntimeError) as error:
        raise ValueError("Повреждённый или неподдерживаемый ZIP навыка.") from error
    missing = set(REQUIRED) - set(extracted)
    if missing:
        raise ValueError("ZIP неполный, отсутствует: " + ", ".join(sorted(missing)))
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    work = Path(tempfile.mkdtemp(prefix=".nikitina-stage-", dir=destination.parent))
    backup = destination.parent / (destination.name + ".previous")
    try:
        for name, content in extracted.items():
            file = work / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(content)
        validated = read_skill(work)
        # Use a reversible rename to avoid leaving a half-installed skill.
        if backup.exists():
            raise ValueError(f"Сначала убери старую резервную папку: {backup}")
        if destination.exists():
            destination.rename(backup)
        try:
            work.rename(destination)
        except OSError:
            if backup.exists() and not destination.exists():
                backup.rename(destination)
            raise
        if backup.exists():
            shutil.rmtree(backup)
        return validated
    finally:
        if work.exists():
            shutil.rmtree(work)
