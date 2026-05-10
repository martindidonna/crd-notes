import { api } from "./client";
import type {
  ChatMessage,
  ChatThread,
  JobStatus,
  KnowledgeFile,
  OperationItem,
  Prompt,
  RecordingSession,
  RecordingSources,
  SettingsResponse,
  WorkspaceIntelligence
} from "./types";

export function listPrompts() {
  return api<Prompt[]>("/api/prompts");
}

export function createJob(form: FormData) {
  return api<{ job_id: string }>("/api/jobs", { method: "POST", body: form });
}

export function getJob(jobId: string) {
  return api<JobStatus>(`/api/jobs/${encodeURIComponent(jobId)}`);
}

export function listRecordingSources() {
  return api<RecordingSources>("/api/recording/sources");
}

export function startRecording(payload: Record<string, unknown>) {
  return api<RecordingSession>("/api/recording/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export function readRecording(sessionId: string) {
  return api<RecordingSession>(`/api/recording/sessions/${encodeURIComponent(sessionId)}`);
}

export function pauseRecording(sessionId: string) {
  return api<RecordingSession>(`/api/recording/sessions/${encodeURIComponent(sessionId)}/pause`, { method: "POST" });
}

export function resumeRecording(sessionId: string) {
  return api<RecordingSession>(`/api/recording/sessions/${encodeURIComponent(sessionId)}/resume`, { method: "POST" });
}

export function addRecordingBookmark(sessionId: string, label = "") {
  return api<RecordingSession>(`/api/recording/sessions/${encodeURIComponent(sessionId)}/bookmarks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ label })
  });
}

export function stopRecording(sessionId: string, promptId: string) {
  return api<{ job_id: string }>(`/api/recording/sessions/${encodeURIComponent(sessionId)}/stop`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ summarize: false, prompt_id: promptId })
  });
}

export function cancelRecording(sessionId: string) {
  return api<void>(`/api/recording/sessions/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
}

export function listOperations(workspaceId: string) {
  return api<OperationItem[]>(`/api/operations?workspace_id=${encodeURIComponent(workspaceId)}`);
}

export function patchOperation(itemId: string, payload: Partial<Pick<OperationItem, "text" | "owner" | "due_date" | "status">>) {
  return api<OperationItem>(`/api/operations/${encodeURIComponent(itemId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export function deleteOperation(itemId: string) {
  return api<{ status: string }>(`/api/operations/${encodeURIComponent(itemId)}`, { method: "DELETE" });
}

export function listKnowledgeFiles(workspaceId: string) {
  return api<KnowledgeFile[]>(`/api/workspaces/${encodeURIComponent(workspaceId)}/knowledge/files`);
}

export function uploadKnowledgeFiles(workspaceId: string, files: File[]) {
  const form = new FormData();
  files.forEach((file) => {
    form.append("files", file);
    form.append("relative_paths", (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name);
  });
  return api<KnowledgeFile[]>(`/api/workspaces/${encodeURIComponent(workspaceId)}/knowledge/files`, {
    method: "POST",
    body: form
  });
}

export function reindexKnowledge(workspaceId: string) {
  return api<{ status: string }>(`/api/workspaces/${encodeURIComponent(workspaceId)}/knowledge/reindex`, {
    method: "POST"
  });
}

export function reindexKnowledgeFile(workspaceId: string, fileId: string) {
  return api<KnowledgeFile>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/knowledge/files/${encodeURIComponent(fileId)}/reindex`,
    { method: "POST" }
  );
}

export function deleteKnowledgeFile(workspaceId: string, fileId: string) {
  return api<void>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/knowledge/files/${encodeURIComponent(fileId)}`,
    { method: "DELETE" }
  );
}

export function getWorkspaceIntelligence(workspaceId: string) {
  return api<WorkspaceIntelligence>(`/api/workspaces/${encodeURIComponent(workspaceId)}/intelligence`);
}

export function createWorkspaceBrief(workspaceId: string) {
  return api<{ brief: string }>(`/api/workspaces/${encodeURIComponent(workspaceId)}/intelligence/ai-brief`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({})
  });
}

export function listChatThreads(workspaceId: string) {
  return api<ChatThread[]>(`/api/workspaces/${encodeURIComponent(workspaceId)}/chat/threads`);
}

export function readChatThread(workspaceId: string, threadId: string) {
  return api<{ thread: ChatThread; messages: ChatMessage[] }>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/chat/threads/${encodeURIComponent(threadId)}`
  );
}

export function createChatThread(workspaceId: string, title = "") {
  return api<ChatThread>(`/api/workspaces/${encodeURIComponent(workspaceId)}/chat/threads`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title })
  });
}

export function deleteChatThread(workspaceId: string, threadId: string) {
  return api<{ ok: boolean }>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/chat/threads/${encodeURIComponent(threadId)}`,
    { method: "DELETE" }
  );
}

export function sendChatMessage(workspaceId: string, threadId: string, content: string) {
  return api<{ thread: ChatThread; messages: ChatMessage[] }>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/chat/threads/${encodeURIComponent(threadId || "new")}/messages`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content, mentioned_entry_ids: [], mentioned_knowledge_folders: [] })
    }
  );
}

export function getSettings() {
  return api<SettingsResponse>("/api/settings");
}

export function saveSettings(settings: Record<string, unknown>) {
  return api<SettingsResponse>("/api/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings)
  });
}
