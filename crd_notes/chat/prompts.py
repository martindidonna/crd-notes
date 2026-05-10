from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PROMPTS_DIR = Path(__file__).resolve().parent / "prompt_templates"
CHAT_SYSTEM_PROMPT_ID = "chat_system"


@dataclass(frozen=True)
class ChatPromptTemplate:
    id: str
    title: str
    description: str
    system_prompt: str


_BUILTIN_CHAT_SYSTEM_PROMPT = """Sei Cardinal, l'assistente AI interno di Cardinal Notes.

Rispondi in italiano, in modo naturale, utile e preciso.
Usa prima il materiale del workspace e la cronologia recente.
Non inventare dettagli non presenti nel materiale disponibile.
Non nominare RAG, retrieval, score, chunk, file o fonti salvo richiesta esplicita.
Quando il materiale non basta, dichiaralo in modo semplice e proponi un passo utile.
"""


def get_chat_system_prompt() -> str:
    return get_chat_prompt(CHAT_SYSTEM_PROMPT_ID).system_prompt


def get_chat_prompt(prompt_id: str = CHAT_SYSTEM_PROMPT_ID) -> ChatPromptTemplate:
    prompts = get_chat_prompts()
    fallback = prompts.get(CHAT_SYSTEM_PROMPT_ID) or ChatPromptTemplate(
        id=CHAT_SYSTEM_PROMPT_ID,
        title="Chat workspace",
        description="Prompt di fallback per la chat del workspace.",
        system_prompt=_BUILTIN_CHAT_SYSTEM_PROMPT,
    )
    return prompts.get(prompt_id) or fallback


def get_chat_prompts() -> dict[str, ChatPromptTemplate]:
    prompts: dict[str, ChatPromptTemplate] = {}
    if not PROMPTS_DIR.exists():
        return prompts
    for prompt_file in sorted(PROMPTS_DIR.glob("*.md")):
        prompt = _load_prompt_file(prompt_file)
        if prompt.id in prompts:
            raise ValueError(f"Prompt chat duplicato: {prompt.id}")
        prompts[prompt.id] = prompt
    return prompts


def build_chat_input(
    *,
    user_message: str,
    rag_context: str,
    rag_evidence: str,
    history: str,
    mentioned_titles: list[str],
    mentioned_folders: list[str],
) -> str:
    mention_block = (
        "\n".join(f"- {title}" for title in mentioned_titles)
        if mentioned_titles
        else "Nessuna riunione taggata."
    )
    has_context = bool(rag_context.strip())
    context_block = rag_context.strip() or "Nessun materiale rilevante trovato."
    evidence_block = rag_evidence.strip() or "Nessun estratto selezionato."
    history_block = history.strip() or "Nessuna cronologia precedente."
    folder_block = (
        "\n".join(f"- {folder}" for folder in mentioned_folders)
        if mentioned_folders
        else "Nessun folder knowledge taggato."
    )
    material_state = "disponibile" if has_context else "non disponibile"
    return (
        "Domanda utente:\n"
        f"{user_message.strip()}\n\n"
        "Riunioni taggate:\n"
        f"{mention_block}\n\n"
        "Folder knowledge taggati:\n"
        f"{folder_block}\n\n"
        "Materiale del workspace:\n"
        f"{context_block}\n\n"
        "Estratti piu' rilevanti:\n"
        f"{evidence_block}\n\n"
        "Disponibilita' materiale:\n"
        f"{material_state}\n\n"
        "Cronologia recente:\n"
        f"{history_block}\n\n"
        "Istruzioni per questa risposta:\n"
        "- Rispondi direttamente alla domanda utente.\n"
        "- Usa il materiale del workspace quando e' disponibile.\n"
        "- Se mancano informazioni decisive, dillo in modo naturale e limitato.\n"
        "- Non citare nomi file, score o dettagli tecnici salvo richiesta esplicita.\n"
        "- Evita tabelle, HTML e rubriche forensi salvo richiesta esplicita.\n"
        "- Mantieni una struttura chiara: paragrafi brevi, elenchi solo quando aiutano.\n\n"
        "Risposta:"
    )


CHAT_QUERY_REWRITE_PROMPT = """Trasforma l'ultimo messaggio utente in una query di ricerca standalone per un sistema RAG.

Regole:
- Rispondi solo con la query, senza spiegazioni.
- Mantieni nomi propri, date, acronimi, file, folder e termini tecnici.
- Usa la cronologia solo per risolvere riferimenti ambigui.
- Non aggiungere fatti non presenti.
"""


def build_query_rewrite_input(
    *,
    user_message: str,
    history: str,
    mentioned_titles: list[str],
    mentioned_folders: list[str],
) -> str:
    return (
        "Cronologia compatta:\n"
        f"{history.strip() or 'Nessuna cronologia.'}\n\n"
        "Riunioni taggate:\n"
        f"{', '.join(mentioned_titles) if mentioned_titles else 'Nessuna'}\n\n"
        "Folder knowledge taggati:\n"
        f"{', '.join(mentioned_folders) if mentioned_folders else 'Nessuno'}\n\n"
        "Messaggio utente:\n"
        f"{user_message.strip()}"
    )


def _load_prompt_file(prompt_file: Path) -> ChatPromptTemplate:
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

    return ChatPromptTemplate(
        id=prompt_id,
        title=title,
        description=description,
        system_prompt=system_prompt,
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
