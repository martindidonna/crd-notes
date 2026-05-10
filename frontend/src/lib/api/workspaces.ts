import { api } from "./client";
import type { Workspace } from "./types";

export function listWorkspaces() {
  return api<Workspace[]>("/api/workspaces");
}

export function createWorkspace(name: string, description = "") {
  return api<Workspace>("/api/workspaces", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description })
  });
}
