# RAG per Workspace

Questa feature introduce una memoria semantica locale per ogni workspace, cosi' da
migliorare qualita' e coerenza di riassunti, chat e flussi conversazionali AI.

L'obiettivo e' recuperare contesto utile da riunioni passate e documenti importati,
senza uscire dall'approccio local-first del progetto.

## Obiettivo

- Creare una memoria unica e isolata per workspace.
- Migliorare riassunti e risposte chat con contesto storico rilevante.
- Indicizzare trascrizioni, riassunti, metadati, elementi operativi e knowledge base.
- Restare locale: vector store, database e modelli embedding girano sulla macchina.

## Flusso end-to-end

### 1. Indicizzazione entry

Quando il RAG e' abilitato, ogni entry puo' produrre documenti indicizzabili:

- `transcript`: trascrizione chunkata.
- `summary`: riassunti AI.
- `metadata`: tag, keyword, persone, topic e contesto.
- `operation`: azioni, decisioni, rischi e domande.
- `note`: titolo, note e partecipanti.

L'indicizzazione avviene durante i workflow applicativi, come upload, generazione
summary, aggiornamento operazioni e reindex manuale.

### 2. Indicizzazione knowledge base

I file knowledge vengono prima parsati in un documento strutturato:

- testo estratto;
- tipo sorgente (`pdf`, `docx`, `xlsx`, `csv`, `text`, `markdown`);
- conteggi tecnici quando disponibili;
- warning non bloccanti;
- metadati utili per diagnosi e retrieval.

Il parser applica limiti su pagine, righe e caratteri estratti. I file `.doc` legacy
non sono accettati come formato affidabile: vanno convertiti in `.docx`, `.pdf`, `.md`
o `.txt`.

### 3. Chunking

Il chunking e' isolato in `crd_notes/rag/chunking.py`.

Ogni chunk conserva:

- testo normalizzato;
- indice progressivo;
- offset parola iniziale e finale.

Questo rende il comportamento testabile e prepara il passaggio futuro a chunking piu'
strutturale per pagine, sezioni e tabelle.

### 4. Retrieval

Il retrieval combina:

- ricerca vettoriale ChromaDB;
- indice lessicale SQLite FTS5;
- filtri per workspace, `doc_type`, entry taggate e folder knowledge;
- reranking locale opzionale con CrossEncoder.

Il risultato viene deduplicato, ordinato e compattato entro `rag.max_context_chars`.

### 5. Consumo nei workflow AI

Il contesto RAG viene usato in:

- enrichment dei summary;
- chat persistente per workspace;
- brief AI del workspace.

La chat costruisce una query compatta usando messaggio corrente, cronologia recente,
mention di riunioni e mention di folder knowledge.

## Tecnologie

### ChromaDB

Usato come vector store locale persistente. Ogni workspace usa una collezione separata.

### SQLite FTS5

Usato come indice lessicale ibrido, utile per acronimi, nomi, date e termini esatti.

### sentence-transformers

Usato per embedding locali e reranking opzionale.

## Configurazione

La sezione `rag` di `AppSettings` controlla:

- `enabled`;
- `storage_dir`;
- `collection_prefix`;
- `embedding_model`;
- `chunk_size_words`;
- `chunk_overlap_words`;
- `top_k`;
- `candidate_k`;
- `max_context_chars`;
- `hybrid_keyword_enabled`;
- `rerank_enabled`;
- `rerank_model`;
- `enrich_summaries`;
- `enrich_with_*`.

## Garanzie

- Isolamento tra workspace.
- Nessun vector database cloud richiesto.
- Parser knowledge con errori espliciti.
- Indicizzazione knowledge meno distruttiva: parsing, chunking ed embedding vengono
  preparati prima di cancellare i vecchi chunk vettoriali.

## Limiti noti

- Non c'e' ancora transazione atomica reale tra ChromaDB e SQLite FTS5.
- Il chunking e' ancora basato su parole, non su struttura del documento.
- PDF complessi, scansioni e tabelle non hanno ancora parser specializzato.
- `.doc` legacy richiede conversione esterna prima dell'import.

## Prossimi step

- Valutare PyMuPDF per PDF complessi.
- Introdurre chunking strutturale per pagine, sezioni e tabelle.
- Aggiungere fixture di retrieval evaluation con query attese.
- Migliorare diagnostica di reindex e metriche sui chunk prodotti.
