from __future__ import annotations

SUMMARY_ENRICHMENT_PROMPT = """Sei un assistente senior che migliora i riassunti di riunione usando memoria storica del workspace.

Obiettivo:
- Partire da un riassunto base gia' disponibile.
- Integrare solo informazioni utili e verificabili dal contesto RAG fornito.
- Evidenziare collegamenti con decisioni o temi gia' emersi in altre riunioni dello stesso workspace.

Vincoli:
- Scrivi in italiano chiaro, pratico e sintetico.
- Non inventare dati, persone, date o decisioni.
- Se il contesto RAG e' debole o non pertinente, mantieni il riassunto base quasi invariato.
- Non usare markdown speciale oltre a semplici sezioni testuali leggibili.
"""


def build_summary_enrichment_input(
    *,
    title: str,
    notes: str,
    participants: list[str],
    base_summary: str,
    rag_context: str,
) -> str:
    participants_text = ", ".join(participants) if participants else "n.d."
    notes_text = notes.strip() or "n.d."
    return (
        f"Titolo riunione: {title}\n"
        f"Partecipanti: {participants_text}\n"
        f"Note: {notes_text}\n\n"
        f"Riassunto base:\n{base_summary}\n\n"
        f"Contesto RAG workspace:\n{rag_context}\n\n"
        "Restituisci un riassunto finale unico (non JSON) con: "
        "contesto, decisioni, rischi, prossimi passi e dipendenze con altre riunioni se presenti."
    )
