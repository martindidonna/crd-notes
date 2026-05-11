import { api, ApiError } from "./client";
import type { LibraryDetail, LibraryEntry, OperationItem, Summary } from "./types";

export type LibraryFilters = {
  q?: string;
  participant?: string;
  keyword?: string;
  date_from?: string;
  date_to?: string;
  summary_filter?: string;
};

export function listLibrary(workspaceId: string, filters: LibraryFilters = {}) {
  const params = new URLSearchParams({ workspace_id: workspaceId });
  Object.entries(filters).forEach(([key, value]) => {
    if (value && value !== "all") params.set(key, value);
  });
  return api<LibraryEntry[]>(`/api/library?${params.toString()}`);
}

export function getLibraryDetail(entryId: string) {
  return api<LibraryDetail>(`/api/library/${encodeURIComponent(entryId)}`);
}

export function createSummary(entryId: string, promptId: string, model = "", provider = "") {
  return api<Summary>(`/api/library/${encodeURIComponent(entryId)}/summaries`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt_id: promptId, model: model || null, provider: provider || null })
  });
}

export type SummaryStreamEvent =
  | { type: "status"; message: string }
  | { type: "delta"; content: string }
  | { type: "replace"; content: string }
  | { type: "done"; summary: Summary }
  | { type: "error"; message: string; detail?: unknown };

export async function createSummaryStream(
  entryId: string,
  promptId: string,
  model = "",
  provider = "",
  onEvent: (event: SummaryStreamEvent) => void
) {
  const response = await fetch(`/api/library/${encodeURIComponent(entryId)}/summaries/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt_id: promptId, model: model || null, provider: provider || null })
  });
  if (!response.ok || !response.body) {
    const data = await response.json().catch(() => ({}));
    throw new ApiError(apiErrorMessage(data), (data as Record<string, unknown>).detail);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.trim()) continue;
      const event = JSON.parse(line) as SummaryStreamEvent;
      onEvent(event);
      if (event.type === "error") {
        throw new ApiError(event.message, event.detail);
      }
    }

    if (done) break;
  }

  if (buffer.trim()) {
    const event = JSON.parse(buffer) as SummaryStreamEvent;
    onEvent(event);
    if (event.type === "error") {
      throw new ApiError(event.message, event.detail);
    }
  }
}

function apiErrorMessage(data: unknown): string {
  if (!data || typeof data !== "object") return "Richiesta non riuscita.";
  const record = data as Record<string, unknown>;
  if (typeof record.message === "string" && record.message.trim()) return record.message;
  if (typeof record.detail === "string" && record.detail.trim()) return record.detail;
  return "Richiesta non riuscita.";
}

export function extractOperations(entryId: string, ai = false) {
  const suffix = ai ? "ai-extract" : "extract";
  return api<{ items: OperationItem[] }>(`/api/library/${encodeURIComponent(entryId)}/operations/${suffix}`, {
    method: "POST"
  });
}
