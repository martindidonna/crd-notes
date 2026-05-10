import { writable } from "svelte/store";
import type {
  KnowledgeFile,
  LibraryEntry,
  OperationItem,
  Prompt,
  Workspace,
  WorkspaceIntelligence
} from "$lib/api/types";

export type AppPage =
  | "work"
  | "operations"
  | "knowledge"
  | "intelligence"
  | "chat"
  | "library"
  | "settings";

export const activePage = writable<AppPage>("work");
export const workspaces = writable<Workspace[]>([]);
export const activeWorkspaceId = writable("default");
export const hasEnteredWorkspace = writable(false);
export const libraryEntries = writable<LibraryEntry[]>([]);
export const prompts = writable<Prompt[]>([]);
export const operations = writable<OperationItem[]>([]);
export const knowledgeFiles = writable<KnowledgeFile[]>([]);
export const workspaceIntelligence = writable<WorkspaceIntelligence | null>(null);
export const appError = writable("");
export const appLoading = writable(false);
