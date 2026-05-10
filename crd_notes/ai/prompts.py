from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PROMPTS_DIR = Path(__file__).resolve().parent / "prompt_templates"
DEFAULT_PROMPT_ID = "sintesi_generale"


@dataclass(frozen=True)
class PromptTemplate:
    id: str
    title: str
    description: str
    system_prompt: str


_BUILTIN_DEFAULT_PROMPT = PromptTemplate(
    id=DEFAULT_PROMPT_ID,
    title="Sintesi generale",
    description="Riassunto leggibile per chi non ha partecipato alla riunione.",
    system_prompt=(
        "Scrivi un riassunto in italiano per una persona che non era presente. Spiega il tema, "
        "le conclusioni e i prossimi passi con linguaggio semplice, senza perdere precisione."
    ),
)


def _split_front_matter(content: str) -> tuple[dict[str, str], str]:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("Front matter mancante.")

    metadata: dict[str, str] = {}
    body_start = -1
    for index, line in enumerate(lines[1:], start=1):
        stripped = line.strip()
        if stripped == "---":
            body_start = index + 1
            break
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()

    if body_start == -1:
        raise ValueError("Chiusura front matter mancante.")

    body = "\n".join(lines[body_start:]).strip()
    return metadata, body


def _load_prompt_file(prompt_file: Path) -> PromptTemplate:
    content = prompt_file.read_text(encoding="utf-8")
    metadata, system_prompt = _split_front_matter(content)

    prompt_id = metadata.get("id", "").strip()
    title = metadata.get("title", "").strip()
    description = metadata.get("description", "").strip()

    if not prompt_id:
        raise ValueError(f"id mancante in {prompt_file.name}.")
    if not title:
        raise ValueError(f"title mancante in {prompt_file.name}.")
    if not description:
        raise ValueError(f"description mancante in {prompt_file.name}.")
    if not system_prompt:
        raise ValueError(f"Contenuto prompt mancante in {prompt_file.name}.")

    return PromptTemplate(
        id=prompt_id,
        title=title,
        description=description,
        system_prompt=system_prompt,
    )


def get_prompts() -> dict[str, PromptTemplate]:
    prompts: dict[str, PromptTemplate] = {}
    for prompt_file in sorted(PROMPTS_DIR.glob("*.md")):
        prompt = _load_prompt_file(prompt_file)
        if prompt.id in prompts:
            raise ValueError(f"Prompt duplicato: {prompt.id}")
        prompts[prompt.id] = prompt
    return prompts


PROMPTS = get_prompts()


def get_prompt(prompt_id: str) -> PromptTemplate:
    prompts = get_prompts()
    fallback = prompts.get(DEFAULT_PROMPT_ID) or _BUILTIN_DEFAULT_PROMPT
    return prompts.get(prompt_id) or fallback
