from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterator

from crd_notes.core.paths import DB_PATH, ensure_data_dirs
from crd_notes.library.models import (
    ChatMessage,
    ChatMessageSource,
    ChatThread,
    DEFAULT_WORKSPACE_ID,
    Job,
    KnowledgeFileStatus,
    LibraryEntry,
    OperationItem,
    Summary,
    SummaryMetadata,
    Workspace,
    WorkspaceKnowledgeFile,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _fts_query(value: str) -> str:
    tokens = re.findall(r"[\wÀ-ÿ]{2,}", value.lower())
    return " OR ".join(dict.fromkeys(tokens[:18]))


class LibraryRepository:
    def __init__(self, path: Path = DB_PATH) -> None:
        self.path = path
        ensure_data_dirs()
        self.migrate()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        self._configure_connection(conn)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _configure_connection(self, conn: sqlite3.Connection) -> None:
        conn.execute("pragma foreign_keys = on")
        conn.execute("pragma busy_timeout = 5000")
        conn.execute("pragma journal_mode = wal")

    def migrate(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                create table if not exists workspaces (
                    id text primary key,
                    name text not null,
                    description text not null,
                    is_default integer not null,
                    created_at text not null,
                    updated_at text not null
                )
                """
            )
            now = utc_now().isoformat()
            conn.execute(
                """
                insert or ignore into workspaces (
                    id, name, description, is_default, created_at, updated_at
                )
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    DEFAULT_WORKSPACE_ID,
                    "Generico",
                    "Workspace predefinito per trascrizioni senza contesto specifico.",
                    1,
                    now,
                    now,
                ),
            )
            conn.execute(
                """
                create table if not exists entries (
                    id text primary key,
                    workspace_id text not null default 'default' references workspaces(id),
                    title text not null,
                    notes text not null,
                    participants text not null,
                    source_filename text not null,
                    audio_filename text,
                    duration_seconds real,
                    recorded_on text,
                    created_at text not null,
                    transcript text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists summaries (
                    id text primary key,
                    entry_id text not null references entries(id) on delete cascade,
                    provider text not null,
                    model text not null,
                    prompt_id text not null,
                    content text not null,
                    created_at text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists jobs (
                    id text primary key,
                    status text not null,
                    stage text not null,
                    progress integer not null,
                    message text not null,
                    error text,
                    entry_id text,
                    payload text not null,
                    created_at text not null,
                    updated_at text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists workspace_knowledge_files (
                    id text primary key,
                    workspace_id text not null references workspaces(id) on delete cascade,
                    original_name text not null,
                    stored_path text not null,
                    content_type text not null,
                    extension text not null,
                    size_bytes integer not null,
                    sha256 text not null,
                    status text not null,
                    error text not null,
                    created_at text not null,
                    updated_at text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists operation_items (
                    id text primary key,
                    entry_id text not null references entries(id) on delete cascade,
                    summary_id text references summaries(id) on delete set null,
                    kind text not null,
                    text text not null,
                    owner text not null,
                    due_date text,
                    status text not null,
                    source text not null,
                    created_at text not null,
                    updated_at text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists summary_metadata (
                    summary_id text primary key references summaries(id) on delete cascade,
                    entry_id text not null references entries(id) on delete cascade,
                    tags text not null,
                    keywords text not null,
                    people text not null,
                    topics text not null,
                    context text not null,
                    created_at text not null,
                    updated_at text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists chat_threads (
                    id text primary key,
                    workspace_id text not null references workspaces(id) on delete cascade,
                    title text not null,
                    created_at text not null,
                    updated_at text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists chat_messages (
                    id text primary key,
                    thread_id text not null references chat_threads(id) on delete cascade,
                    role text not null,
                    content text not null,
                    provider text not null,
                    model text not null,
                    created_at text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists chat_message_sources (
                    id text primary key,
                    message_id text not null references chat_messages(id) on delete cascade,
                    entry_id text not null,
                    entry_title text not null,
                    doc_type text not null,
                    source text not null,
                    score real not null,
                    snippet text not null,
                    created_at text not null
                )
                """
            )
            conn.execute(
                """
                create virtual table if not exists rag_keyword_index
                using fts5(
                    doc_id unindexed,
                    workspace_id unindexed,
                    entry_id unindexed,
                    entry_title unindexed,
                    doc_type unindexed,
                    source unindexed,
                    knowledge_folder unindexed,
                    content,
                    tokenize='unicode61 remove_diacritics 2'
                )
                """
            )
            columns = {
                row["name"]
                for row in conn.execute("pragma table_info(entries)").fetchall()
            }
            if "recorded_on" not in columns:
                conn.execute("alter table entries add column recorded_on text")
            if "workspace_id" not in columns:
                conn.execute(
                    "alter table entries add column workspace_id text not null default 'default'"
                )
            conn.execute(
                "update entries set workspace_id = ? where workspace_id is null or workspace_id = ''",
                (DEFAULT_WORKSPACE_ID,),
            )
            conn.execute("create index if not exists idx_entries_workspace on entries(workspace_id)")
            conn.execute("create index if not exists idx_entries_recorded_on on entries(recorded_on)")
            conn.execute("create index if not exists idx_summaries_entry on summaries(entry_id)")
            conn.execute("create index if not exists idx_operations_entry on operation_items(entry_id)")
            conn.execute("create index if not exists idx_summary_metadata_entry on summary_metadata(entry_id)")
            conn.execute(
                "create index if not exists idx_knowledge_workspace on workspace_knowledge_files(workspace_id)"
            )
            conn.execute(
                "create index if not exists idx_knowledge_sha on workspace_knowledge_files(workspace_id, sha256)"
            )
            conn.execute("create index if not exists idx_chat_threads_workspace on chat_threads(workspace_id, updated_at)")
            conn.execute("create index if not exists idx_chat_messages_thread on chat_messages(thread_id, created_at)")
            conn.execute("create index if not exists idx_chat_sources_message on chat_message_sources(message_id)")

    def add_workspace(self, workspace: Workspace) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                insert into workspaces (
                    id, name, description, is_default, created_at, updated_at
                )
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    workspace.id,
                    workspace.name,
                    workspace.description,
                    1 if workspace.is_default else 0,
                    workspace.created_at.isoformat(),
                    workspace.updated_at.isoformat(),
                ),
            )

    def list_workspaces(self) -> list[Workspace]:
        with self.connect() as conn:
            rows = conn.execute(
                "select * from workspaces order by is_default desc, name collate nocase"
            ).fetchall()
        return [self._workspace_from_row(row) for row in rows]

    def get_workspace(self, workspace_id: str) -> Workspace | None:
        with self.connect() as conn:
            row = conn.execute(
                "select * from workspaces where id = ?",
                (workspace_id,),
            ).fetchone()
        return self._workspace_from_row(row) if row else None

    def add_workspace_knowledge_file(self, file: WorkspaceKnowledgeFile) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                insert into workspace_knowledge_files (
                    id,
                    workspace_id,
                    original_name,
                    stored_path,
                    content_type,
                    extension,
                    size_bytes,
                    sha256,
                    status,
                    error,
                    created_at,
                    updated_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file.id,
                    file.workspace_id,
                    file.original_name,
                    file.stored_path,
                    file.content_type,
                    file.extension,
                    file.size_bytes,
                    file.sha256,
                    file.status,
                    file.error,
                    file.created_at.isoformat(),
                    file.updated_at.isoformat(),
                ),
            )

    def list_workspace_knowledge_files(self, workspace_id: str) -> list[WorkspaceKnowledgeFile]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                select *
                from workspace_knowledge_files
                where workspace_id = ?
                order by created_at desc
                """,
                (workspace_id,),
            ).fetchall()
        return [self._knowledge_file_from_row(row) for row in rows]

    def get_workspace_knowledge_file(self, file_id: str) -> WorkspaceKnowledgeFile | None:
        with self.connect() as conn:
            row = conn.execute(
                "select * from workspace_knowledge_files where id = ?",
                (file_id,),
            ).fetchone()
        return self._knowledge_file_from_row(row) if row else None

    def find_workspace_knowledge_file_by_hash(
        self,
        *,
        workspace_id: str,
        sha256: str,
    ) -> WorkspaceKnowledgeFile | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                select *
                from workspace_knowledge_files
                where workspace_id = ? and sha256 = ?
                limit 1
                """,
                (workspace_id, sha256),
            ).fetchone()
        return self._knowledge_file_from_row(row) if row else None

    def update_workspace_knowledge_file_status(
        self,
        file_id: str,
        *,
        status: KnowledgeFileStatus,
        error: str = "",
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                update workspace_knowledge_files
                set status = ?, error = ?, updated_at = ?
                where id = ?
                """,
                (status, error, utc_now().isoformat(), file_id),
            )

    def delete_workspace_knowledge_file(self, file_id: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "delete from workspace_knowledge_files where id = ?",
                (file_id,),
            )

    def add_entry(self, entry: LibraryEntry) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                insert into entries (
                    id, workspace_id, title, notes, participants, source_filename, audio_filename,
                    duration_seconds, recorded_on, created_at, transcript
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.id,
                    entry.workspace_id,
                    entry.title,
                    entry.notes,
                    json.dumps(entry.participants, ensure_ascii=False),
                    entry.source_filename,
                    entry.audio_filename,
                    entry.duration_seconds,
                    entry.recorded_on.isoformat() if entry.recorded_on else None,
                    entry.created_at.isoformat(),
                    entry.transcript,
                ),
            )

    def list_entries(
        self,
        workspace_id: str | None = None,
        *,
        query: str = "",
        participant: str = "",
        keyword: str = "",
        date_from: date | None = None,
        date_to: date | None = None,
        summary_filter: str = "all",
        include_transcript: bool = True,
    ) -> list[LibraryEntry]:
        like = f"%{query.strip()}%" if query.strip() else ""
        keyword_like = f"%{keyword.strip()}%" if keyword.strip() else ""
        participant_like = f"%{participant.strip()}%" if participant.strip() else ""
        columns = "entries.*" if include_transcript else """
                  entries.id,
                  entries.workspace_id,
                  entries.title,
                  entries.notes,
                  entries.participants,
                  entries.source_filename,
                  entries.audio_filename,
                  entries.duration_seconds,
                  entries.recorded_on,
                  entries.created_at,
                  '' as transcript
                """
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                select distinct {columns}
                from entries
                left join summaries on summaries.entry_id = entries.id
                left join summary_metadata on summary_metadata.entry_id = entries.id
                where (? is null or entries.workspace_id = ?)
                  and (
                    ? = ''
                    or entries.title like ?
                    or entries.notes like ?
                    or entries.participants like ?
                    or entries.transcript like ?
                    or summaries.content like ?
                    or summary_metadata.tags like ?
                    or summary_metadata.keywords like ?
                    or summary_metadata.people like ?
                    or summary_metadata.topics like ?
                    or summary_metadata.context like ?
                  )
                  and (? = '' or entries.participants like ? or summary_metadata.people like ?)
                  and (? = '' or summary_metadata.tags like ? or summary_metadata.keywords like ? or summary_metadata.topics like ?)
                  and (? is null or entries.recorded_on >= ?)
                  and (? is null or entries.recorded_on <= ?)
                  and (
                    ? = 'all'
                    or (? = 'with' and summaries.id is not null)
                    or (? = 'without' and summaries.id is null)
                  )
                order by entries.created_at desc
                """,
                (
                    workspace_id,
                    workspace_id,
                    like,
                    like,
                    like,
                    like,
                    like,
                    like,
                    like,
                    like,
                    like,
                    like,
                    like,
                    participant_like,
                    participant_like,
                    participant_like,
                    keyword_like,
                    keyword_like,
                    keyword_like,
                    keyword_like,
                    date_from.isoformat() if date_from else None,
                    date_from.isoformat() if date_from else None,
                    date_to.isoformat() if date_to else None,
                    date_to.isoformat() if date_to else None,
                    summary_filter,
                    summary_filter,
                    summary_filter,
                ),
            ).fetchall()
        return [self._entry_from_row(row) for row in rows]

    def entry_metadata(self) -> dict[str, dict[str, list[str] | str]]:
        metadata: dict[str, dict[str, list[str] | str]] = {}
        with self.connect() as conn:
            rows = conn.execute(
                """
                select * from summary_metadata
                order by updated_at desc
                """
            ).fetchall()
        for row in rows:
            current = metadata.setdefault(
                row["entry_id"],
                {"tags": [], "keywords": [], "people": [], "topics": [], "context": ""},
            )
            for field in ("tags", "keywords", "people", "topics"):
                values = current[field]
                assert isinstance(values, list)
                for value in json.loads(row[field]):
                    if value not in values:
                        values.append(value)
            if not current["context"]:
                current["context"] = row["context"]
        return metadata

    def library_counts(self) -> dict[str, dict[str, int]]:
        counts: dict[str, dict[str, int]] = {}
        with self.connect() as conn:
            summary_rows = conn.execute(
                "select entry_id, count(*) as count from summaries group by entry_id"
            ).fetchall()
            operation_rows = conn.execute(
                """
                select
                    entry_id,
                    count(*) as total_count,
                    sum(case when status = 'open' then 1 else 0 end) as open_count
                from operation_items
                group by entry_id
                """
            ).fetchall()
        for row in summary_rows:
            counts.setdefault(row["entry_id"], {})["summary_count"] = int(row["count"] or 0)
        for row in operation_rows:
            entry_counts = counts.setdefault(row["entry_id"], {})
            entry_counts["operation_total_count"] = int(row["total_count"] or 0)
            entry_counts["operation_open_count"] = int(row["open_count"] or 0)
        return counts

    def get_entry(self, entry_id: str) -> LibraryEntry | None:
        with self.connect() as conn:
            row = conn.execute("select * from entries where id = ?", (entry_id,)).fetchone()
        return self._entry_from_row(row) if row else None

    def add_summary(self, summary: Summary) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                insert into summaries (
                    id, entry_id, provider, model, prompt_id, content, created_at
                )
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    summary.id,
                    summary.entry_id,
                    summary.provider,
                    summary.model,
                    summary.prompt_id,
                    summary.content,
                    summary.created_at.isoformat(),
                ),
            )

    def list_summaries(self, entry_id: str) -> list[Summary]:
        with self.connect() as conn:
            rows = conn.execute(
                "select * from summaries where entry_id = ? order by created_at desc",
                (entry_id,),
            ).fetchall()
        return [self._summary_from_row(row) for row in rows]

    def add_summary_metadata(self, metadata: SummaryMetadata) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                insert into summary_metadata (
                    summary_id, entry_id, tags, keywords, people, topics,
                    context, created_at, updated_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(summary_id) do update set
                    tags = excluded.tags,
                    keywords = excluded.keywords,
                    people = excluded.people,
                    topics = excluded.topics,
                    context = excluded.context,
                    updated_at = excluded.updated_at
                """,
                (
                    metadata.summary_id,
                    metadata.entry_id,
                    json.dumps(metadata.tags, ensure_ascii=False),
                    json.dumps(metadata.keywords, ensure_ascii=False),
                    json.dumps(metadata.people, ensure_ascii=False),
                    json.dumps(metadata.topics, ensure_ascii=False),
                    metadata.context,
                    metadata.created_at.isoformat(),
                    metadata.updated_at.isoformat(),
                ),
            )

    def get_summary_metadata(self, summary_id: str) -> SummaryMetadata | None:
        with self.connect() as conn:
            row = conn.execute(
                "select * from summary_metadata where summary_id = ?",
                (summary_id,),
            ).fetchone()
        return self._summary_metadata_from_row(row) if row else None

    def list_summary_metadata(self, entry_id: str) -> dict[str, SummaryMetadata]:
        with self.connect() as conn:
            rows = conn.execute(
                "select * from summary_metadata where entry_id = ?",
                (entry_id,),
            ).fetchall()
        return {row["summary_id"]: self._summary_metadata_from_row(row) for row in rows}

    def add_operation_item(self, item: OperationItem) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                insert into operation_items (
                    id, entry_id, summary_id, kind, text, owner, due_date,
                    status, source, created_at, updated_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.entry_id,
                    item.summary_id,
                    item.kind,
                    item.text,
                    item.owner,
                    item.due_date.isoformat() if item.due_date else None,
                    item.status,
                    item.source,
                    item.created_at.isoformat(),
                    item.updated_at.isoformat(),
                ),
            )

    def add_operation_items(self, items: list[OperationItem]) -> None:
        if not items:
            return
        with self.connect() as conn:
            conn.executemany(
                """
                insert into operation_items (
                    id, entry_id, summary_id, kind, text, owner, due_date,
                    status, source, created_at, updated_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.id,
                        item.entry_id,
                        item.summary_id,
                        item.kind,
                        item.text,
                        item.owner,
                        item.due_date.isoformat() if item.due_date else None,
                        item.status,
                        item.source,
                        item.created_at.isoformat(),
                        item.updated_at.isoformat(),
                    )
                    for item in items
                ],
            )

    def list_operation_items(
        self,
        *,
        workspace_id: str | None = None,
        entry_id: str | None = None,
        summary_id: str | None = None,
        source: str | None = None,
    ) -> list[OperationItem]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                select * from operation_items
                where (? is null or entry_id = ?)
                  and (? is null or summary_id = ?)
                  and (? is null or source = ?)
                  and (
                    ? is null
                    or exists (
                        select 1 from entries
                        where entries.id = operation_items.entry_id
                          and entries.workspace_id = ?
                    )
                  )
                order by created_at desc
                """,
                (
                    entry_id,
                    entry_id,
                    summary_id,
                    summary_id,
                    source,
                    source,
                    workspace_id,
                    workspace_id,
                ),
            ).fetchall()
        return [self._operation_from_row(row) for row in rows]

    def get_operation_item(self, item_id: str) -> OperationItem | None:
        with self.connect() as conn:
            row = conn.execute(
                "select * from operation_items where id = ?",
                (item_id,),
            ).fetchone()
        return self._operation_from_row(row) if row else None

    def update_operation_item(
        self,
        item_id: str,
        *,
        text: str | None = None,
        owner: str | None = None,
        due_date: date | None = None,
        status: str | None = None,
    ) -> OperationItem | None:
        current = self.get_operation_item(item_id)
        if current is None:
            return None
        with self.connect() as conn:
            conn.execute(
                """
                update operation_items
                set text = ?, owner = ?, due_date = ?, status = ?, updated_at = ?
                where id = ?
                """,
                (
                    text if text is not None else current.text,
                    owner if owner is not None else current.owner,
                    due_date.isoformat() if due_date else None,
                    status if status is not None else current.status,
                    utc_now().isoformat(),
                    item_id,
                ),
            )
        return self.get_operation_item(item_id)

    def delete_operation_item(self, item_id: str) -> None:
        with self.connect() as conn:
            conn.execute("delete from operation_items where id = ?", (item_id,))

    def delete_operation_items(
        self,
        *,
        entry_id: str,
        summary_id: str | None,
        source: str,
    ) -> None:
        with self.connect() as conn:
            if summary_id is None:
                conn.execute(
                    "delete from operation_items where entry_id = ? and summary_id is null and source = ?",
                    (entry_id, source),
                )
            else:
                conn.execute(
                    "delete from operation_items where entry_id = ? and summary_id = ? and source = ?",
                    (entry_id, summary_id, source),
                )

    def replace_rag_keyword_docs(self, *, workspace_id: str, entry_id: str, docs: list[dict]) -> None:
        with self.connect() as conn:
            conn.execute(
                "delete from rag_keyword_index where workspace_id = ? and entry_id = ?",
                (workspace_id, entry_id),
            )
            self._insert_rag_keyword_docs(conn, docs)

    def replace_rag_keyword_knowledge_docs(
        self,
        *,
        workspace_id: str,
        knowledge_file_id: str,
        docs: list[dict],
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                "delete from rag_keyword_index where workspace_id = ? and entry_id = ?",
                (workspace_id, knowledge_file_id),
            )
            self._insert_rag_keyword_docs(conn, docs)

    def clear_workspace_rag_keyword_docs(self, workspace_id: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "delete from rag_keyword_index where workspace_id = ?",
                (workspace_id,),
            )

    def delete_rag_keyword_docs(self, *, workspace_id: str, entry_id: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "delete from rag_keyword_index where workspace_id = ? and entry_id = ?",
                (workspace_id, entry_id),
            )

    def search_rag_keyword_docs(
        self,
        *,
        workspace_id: str,
        query: str,
        doc_types: list[str] | None = None,
        entry_ids: list[str] | None = None,
        knowledge_folders: list[str] | None = None,
        limit: int = 20,
    ) -> list[dict]:
        clean_query = _fts_query(query)
        if not clean_query:
            return []
        clauses = ["workspace_id = ?", "rag_keyword_index match ?"]
        params: list[object] = [workspace_id, clean_query]
        if doc_types:
            clauses.append(f"doc_type in ({','.join(['?'] * len(doc_types))})")
            params.extend(doc_types)
        if entry_ids:
            clauses.append(f"entry_id in ({','.join(['?'] * len(entry_ids))})")
            params.extend(entry_ids)
        if knowledge_folders:
            clauses.append(f"knowledge_folder in ({','.join(['?'] * len(knowledge_folders))})")
            params.extend(knowledge_folders)
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                select
                    doc_id,
                    workspace_id,
                    entry_id,
                    entry_title,
                    doc_type,
                    source,
                    knowledge_folder,
                    content,
                    bm25(rag_keyword_index) as rank
                from rag_keyword_index
                where {' and '.join(clauses)}
                order by rank
                limit ?
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def _insert_rag_keyword_docs(self, conn: sqlite3.Connection, docs: list[dict]) -> None:
        if not docs:
            return
        conn.executemany(
            """
            insert into rag_keyword_index (
                doc_id,
                workspace_id,
                entry_id,
                entry_title,
                doc_type,
                source,
                knowledge_folder,
                content
            )
            values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    doc.get("doc_id", ""),
                    doc.get("workspace_id", ""),
                    doc.get("entry_id", ""),
                    doc.get("entry_title", ""),
                    doc.get("doc_type", ""),
                    doc.get("source", ""),
                    doc.get("knowledge_folder", ""),
                    doc.get("content", ""),
                )
                for doc in docs
            ],
        )

    def add_chat_thread(self, thread: ChatThread) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                insert into chat_threads (id, workspace_id, title, created_at, updated_at)
                values (?, ?, ?, ?, ?)
                """,
                (
                    thread.id,
                    thread.workspace_id,
                    thread.title,
                    thread.created_at.isoformat(),
                    thread.updated_at.isoformat(),
                ),
            )

    def list_chat_threads(self, workspace_id: str) -> list[ChatThread]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                select *
                from chat_threads
                where workspace_id = ?
                order by updated_at desc
                """,
                (workspace_id,),
            ).fetchall()
        return [self._chat_thread_from_row(row) for row in rows]

    def get_chat_thread(self, thread_id: str) -> ChatThread | None:
        with self.connect() as conn:
            row = conn.execute(
                "select * from chat_threads where id = ?",
                (thread_id,),
            ).fetchone()
        return self._chat_thread_from_row(row) if row else None

    def update_chat_thread(
        self,
        thread_id: str,
        *,
        title: str | None = None,
        updated_at: datetime | None = None,
    ) -> ChatThread | None:
        current = self.get_chat_thread(thread_id)
        if current is None:
            return None
        next_updated_at = updated_at or utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                update chat_threads
                set title = ?, updated_at = ?
                where id = ?
                """,
                (
                    title if title is not None else current.title,
                    next_updated_at.isoformat(),
                    thread_id,
                ),
            )
        return self.get_chat_thread(thread_id)

    def delete_chat_thread(self, thread_id: str) -> None:
        with self.connect() as conn:
            conn.execute("delete from chat_threads where id = ?", (thread_id,))

    def add_chat_message(self, message: ChatMessage) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                insert into chat_messages (
                    id, thread_id, role, content, provider, model, created_at
                )
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.id,
                    message.thread_id,
                    message.role,
                    message.content,
                    message.provider,
                    message.model,
                    message.created_at.isoformat(),
                ),
            )

    def list_chat_messages(self, thread_id: str) -> list[ChatMessage]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                select *
                from chat_messages
                where thread_id = ?
                order by created_at
                """,
                (thread_id,),
            ).fetchall()
        return [self._chat_message_from_row(row) for row in rows]

    def add_chat_message_sources(self, sources: list[ChatMessageSource]) -> None:
        if not sources:
            return
        with self.connect() as conn:
            conn.executemany(
                """
                insert into chat_message_sources (
                    id, message_id, entry_id, entry_title, doc_type, source,
                    score, snippet, created_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        source.id,
                        source.message_id,
                        source.entry_id,
                        source.entry_title,
                        source.doc_type,
                        source.source,
                        source.score,
                        source.snippet,
                        source.created_at.isoformat(),
                    )
                    for source in sources
                ],
            )

    def list_chat_message_sources(self, message_id: str) -> list[ChatMessageSource]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                select *
                from chat_message_sources
                where message_id = ?
                order by score desc, created_at
                """,
                (message_id,),
            ).fetchall()
        return [self._chat_message_source_from_row(row) for row in rows]

    def list_chat_sources_for_thread(self, thread_id: str) -> dict[str, list[ChatMessageSource]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                select chat_message_sources.*
                from chat_message_sources
                join chat_messages on chat_messages.id = chat_message_sources.message_id
                where chat_messages.thread_id = ?
                order by chat_message_sources.score desc, chat_message_sources.created_at
                """,
                (thread_id,),
            ).fetchall()
        grouped: dict[str, list[ChatMessageSource]] = {}
        for row in rows:
            source = self._chat_message_source_from_row(row)
            grouped.setdefault(source.message_id, []).append(source)
        return grouped

    def create_job(self, job: Job) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                insert into jobs (
                    id, status, stage, progress, message, error, entry_id,
                    payload, created_at, updated_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.id,
                    job.status,
                    job.stage,
                    job.progress,
                    job.message,
                    job.error,
                    job.entry_id,
                    json.dumps(job.payload, ensure_ascii=False),
                    job.created_at.isoformat(),
                    job.updated_at.isoformat(),
                ),
            )

    def update_job(
        self,
        job_id: str,
        *,
        status: str | None = None,
        stage: str | None = None,
        progress: int | None = None,
        message: str | None = None,
        error: str | None = None,
        entry_id: str | None = None,
    ) -> None:
        current = self.get_job(job_id)
        if current is None:
            return

        with self.connect() as conn:
            conn.execute(
                """
                update jobs
                set status = ?, stage = ?, progress = ?, message = ?, error = ?,
                    entry_id = ?, updated_at = ?
                where id = ?
                """,
                (
                    status if status is not None else current.status,
                    stage if stage is not None else current.stage,
                    progress if progress is not None else current.progress,
                    message if message is not None else current.message,
                    error,
                    entry_id if entry_id is not None else current.entry_id,
                    utc_now().isoformat(),
                    job_id,
                ),
            )

    def get_job(self, job_id: str) -> Job | None:
        with self.connect() as conn:
            row = conn.execute("select * from jobs where id = ?", (job_id,)).fetchone()
        return self._job_from_row(row) if row else None

    def list_open_jobs(self) -> list[Job]:
        with self.connect() as conn:
            rows = conn.execute(
                "select * from jobs where status in ('queued', 'running') order by created_at"
            ).fetchall()
        return [self._job_from_row(row) for row in rows]

    def _entry_from_row(self, row: sqlite3.Row) -> LibraryEntry:
        return LibraryEntry(
            id=row["id"],
            workspace_id=row["workspace_id"] or DEFAULT_WORKSPACE_ID,
            title=row["title"],
            notes=row["notes"],
            participants=json.loads(row["participants"]),
            source_filename=row["source_filename"],
            audio_filename=row["audio_filename"],
            duration_seconds=row["duration_seconds"],
            recorded_on=parse_date(row["recorded_on"]),
            created_at=parse_dt(row["created_at"]),
            transcript=row["transcript"],
        )

    def _workspace_from_row(self, row: sqlite3.Row) -> Workspace:
        return Workspace(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            is_default=bool(row["is_default"]),
            created_at=parse_dt(row["created_at"]),
            updated_at=parse_dt(row["updated_at"]),
        )

    def _summary_from_row(self, row: sqlite3.Row) -> Summary:
        return Summary(
            id=row["id"],
            entry_id=row["entry_id"],
            provider=row["provider"],
            model=row["model"],
            prompt_id=row["prompt_id"],
            content=row["content"],
            created_at=parse_dt(row["created_at"]),
        )

    def _summary_metadata_from_row(self, row: sqlite3.Row) -> SummaryMetadata:
        return SummaryMetadata(
            summary_id=row["summary_id"],
            entry_id=row["entry_id"],
            tags=json.loads(row["tags"]),
            keywords=json.loads(row["keywords"]),
            people=json.loads(row["people"]),
            topics=json.loads(row["topics"]),
            context=row["context"],
            created_at=parse_dt(row["created_at"]),
            updated_at=parse_dt(row["updated_at"]),
        )

    def _operation_from_row(self, row: sqlite3.Row) -> OperationItem:
        return OperationItem(
            id=row["id"],
            entry_id=row["entry_id"],
            summary_id=row["summary_id"],
            kind=row["kind"],
            text=row["text"],
            owner=row["owner"],
            due_date=parse_date(row["due_date"]),
            status=row["status"],
            source=row["source"],
            created_at=parse_dt(row["created_at"]),
            updated_at=parse_dt(row["updated_at"]),
        )

    def _job_from_row(self, row: sqlite3.Row) -> Job:
        return Job(
            id=row["id"],
            status=row["status"],
            stage=row["stage"],
            progress=row["progress"],
            message=row["message"],
            error=row["error"],
            entry_id=row["entry_id"],
            payload=json.loads(row["payload"]),
            created_at=parse_dt(row["created_at"]),
            updated_at=parse_dt(row["updated_at"]),
        )

    def _knowledge_file_from_row(self, row: sqlite3.Row) -> WorkspaceKnowledgeFile:
        return WorkspaceKnowledgeFile(
            id=row["id"],
            workspace_id=row["workspace_id"],
            original_name=row["original_name"],
            stored_path=row["stored_path"],
            content_type=row["content_type"],
            extension=row["extension"],
            size_bytes=row["size_bytes"],
            sha256=row["sha256"],
            status=row["status"],
            error=row["error"],
            created_at=parse_dt(row["created_at"]),
            updated_at=parse_dt(row["updated_at"]),
        )

    def _chat_thread_from_row(self, row: sqlite3.Row) -> ChatThread:
        return ChatThread(
            id=row["id"],
            workspace_id=row["workspace_id"],
            title=row["title"],
            created_at=parse_dt(row["created_at"]),
            updated_at=parse_dt(row["updated_at"]),
        )

    def _chat_message_from_row(self, row: sqlite3.Row) -> ChatMessage:
        return ChatMessage(
            id=row["id"],
            thread_id=row["thread_id"],
            role=row["role"],
            content=row["content"],
            provider=row["provider"],
            model=row["model"],
            created_at=parse_dt(row["created_at"]),
        )

    def _chat_message_source_from_row(self, row: sqlite3.Row) -> ChatMessageSource:
        return ChatMessageSource(
            id=row["id"],
            message_id=row["message_id"],
            entry_id=row["entry_id"],
            entry_title=row["entry_title"],
            doc_type=row["doc_type"],
            source=row["source"],
            score=row["score"],
            snippet=row["snippet"],
            created_at=parse_dt(row["created_at"]),
        )
