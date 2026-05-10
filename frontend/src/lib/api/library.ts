import { api } from "./client";
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

export function extractOperations(entryId: string, ai = false) {
  const suffix = ai ? "ai-extract" : "extract";
  return api<{ items: OperationItem[] }>(`/api/library/${encodeURIComponent(entryId)}/operations/${suffix}`, {
    method: "POST"
  });
}
