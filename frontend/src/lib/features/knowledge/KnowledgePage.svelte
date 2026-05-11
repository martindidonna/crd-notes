<script lang="ts">
  import { FileUp, FolderUp, RefreshCw, Trash2 } from "lucide-svelte";
  import { Button } from "$lib/components/ui/button";
  import type { KnowledgeFile } from "$lib/api/types";

  export let files: KnowledgeFile[] = [];
  export let message = "";
  export let errors: string[] = [];
  export let busy = false;
  export let busyMessage = "";
  export let onUpload: (files: File[]) => Promise<void>;
  export let onReindexAll: () => Promise<void>;
  export let onReindexFile: (fileId: string) => Promise<void>;
  export let onDeleteFile: (fileId: string) => Promise<void>;
  let selected: File[] = [];

  type TreeNode<T> = {
    name: string;
    path: string;
    folders: TreeNode<T>[];
    files: Array<{ name: string; path: string; item: T }>;
  };

  const allowedExtensions = new Set([".pdf", ".doc", ".docx", ".txt", ".md", ".xls", ".xlsx", ".csv"]);

  function extensionOf(path: string) {
    const index = path.lastIndexOf(".");
    return index >= 0 ? path.slice(index).toLowerCase() : "";
  }

  function relativePathOf(file: File) {
    return ((file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name).replaceAll("\\", "/");
  }

  function addSelection(fileList: FileList | null) {
    if (busy) return;
    const incoming = Array.from(fileList ?? []).filter((file) => allowedExtensions.has(extensionOf(relativePathOf(file))));
    const byPath = new Map(selected.map((file) => [relativePathOf(file).toLowerCase(), file]));
    incoming.forEach((file) => byPath.set(relativePathOf(file).toLowerCase(), file));
    selected = Array.from(byPath.values()).sort((a, b) => relativePathOf(a).localeCompare(relativePathOf(b), "it"));
  }

  function removeSelection(path: string) {
    if (busy) return;
    selected = selected.filter((file) => relativePathOf(file) !== path);
  }

  async function importSelected() {
    if (busy || !selected.length) return;
    try {
      await onUpload(selected);
      selected = [];
    } catch {
      // Parent owns visible import errors; keep the selection so the user can fix it.
    }
  }

  function buildTree<T>(items: T[], pathOf: (item: T) => string): TreeNode<T> {
    const root: TreeNode<T> = { name: "", path: "", folders: [], files: [] };
    const folderMap = new Map<string, TreeNode<T>>([["", root]]);
    for (const item of items) {
      const path = pathOf(item).replaceAll("\\", "/");
      const parts = path.split("/").filter(Boolean);
      if (!parts.length) continue;
      let parent = root;
      let currentPath = "";
      for (const folder of parts.slice(0, -1)) {
        currentPath = currentPath ? `${currentPath}/${folder}` : folder;
        let node = folderMap.get(currentPath);
        if (!node) {
          node = { name: folder, path: currentPath, folders: [], files: [] };
          folderMap.set(currentPath, node);
          parent.folders.push(node);
        }
        parent = node;
      }
      parent.files.push({ name: parts.at(-1) ?? path, path, item });
    }
    sortTree(root);
    return root;
  }

  function sortTree<T>(node: TreeNode<T>) {
    node.folders.sort((a, b) => a.name.localeCompare(b.name, "it"));
    node.files.sort((a, b) => a.name.localeCompare(b.name, "it"));
    node.folders.forEach(sortTree);
  }

  function countTree<T>(node: TreeNode<T>): number {
    return node.files.length + node.folders.reduce((total, folder) => total + countTree(folder), 0);
  }

  function formatBytes(value: number) {
    if (!value) return "0 B";
    const units = ["B", "KB", "MB", "GB"];
    let amount = value;
    let index = 0;
    while (amount >= 1024 && index < units.length - 1) {
      amount /= 1024;
      index += 1;
    }
    return `${index ? amount.toFixed(1) : Math.round(amount)} ${units[index]}`;
  }

  $: selectedTree = buildTree(selected, relativePathOf);
  $: fileTree = buildTree(files, (file) => file.original_name || file.id);
  $: selectedSize = selected.reduce((total, file) => total + file.size, 0);
  $: statusMessage = busy
    ? busyMessage || "Backend al lavoro sulla knowledge."
    : selected.length
      ? `${selected.length} file pronti per l'import - ${formatBytes(selectedSize)}`
      : message || "Nessun file selezionato.";
</script>

<section class="knowledge-page-layout">
  <section class="process-panel">
    <div class="section-heading-line">
      <div>
        <p class="eyebrow">Knowledge inserita dall'utente</p>
        <h2>Base stabile del workspace</h2>
        <p class="muted">File e cartelle aggiunti manualmente al workspace.</p>
      </div>
      <Button variant="secondary" disabled={busy} on:click={onReindexAll}><RefreshCw size={15} />Ricalcola memoria</Button>
    </div>
    {#if busy}
      <div class="knowledge-backend-status" role="status" aria-live="polite">
        <span aria-hidden="true"></span>
        <strong>{busyMessage || "Backend al lavoro sulla knowledge."}</strong>
      </div>
    {/if}
    {#if errors.length}
      <div class="knowledge-error-list" role="alert" aria-live="assertive">
        <strong>{errors.length === 1 ? "Errore import knowledge" : "Errori import knowledge"}</strong>
        <ul>
          {#each errors as error}
            <li>{error}</li>
          {/each}
        </ul>
      </div>
    {/if}
    <div class="knowledge-upload-controls">
      <label class="knowledge-input-group" class:disabled={busy}>
        <FileUp size={22} />
        <span><strong>Seleziona file</strong><small>PDF, Word, TXT, Markdown, Excel e CSV.</small></span>
        <input type="file" accept=".pdf,.doc,.docx,.txt,.md,.xls,.xlsx,.csv" multiple disabled={busy} on:change={(event) => addSelection(event.currentTarget.files)} />
      </label>
      <label class="knowledge-input-group" class:disabled={busy}>
        <FolderUp size={22} />
        <span><strong>Importa cartella</strong><small>Mantiene percorsi relativi e sottocartelle.</small></span>
        <input type="file" accept=".pdf,.doc,.docx,.txt,.md,.xls,.xlsx,.csv" multiple webkitdirectory directory disabled={busy} on:change={(event) => addSelection(event.currentTarget.files)} />
      </label>
    </div>
    <div class="knowledge-selection-bar">
      <p class="settings-note">{statusMessage}</p>
      <Button disabled={busy || !selected.length} on:click={importSelected}>{busy ? "Import in corso" : "Importa nella knowledge"}</Button>
    </div>
    {#if selected.length}
      <div class="knowledge-upload-preview">
        {@render TreeView(selectedTree, 0, "selection", removeSelection)}
      </div>
    {/if}
    <div class="knowledge-files">
      {#if files.length}
        {@render TreeView(fileTree, 0, "stored", undefined, onReindexFile, onDeleteFile)}
      {:else}
        <p class="empty">Nessun documento utente importato in questo workspace.</p>
      {/if}
    </div>
  </section>
</section>

{#snippet TreeView(node: TreeNode<File | KnowledgeFile>, depth: number, mode: "selection" | "stored", onRemoveSelection?: (path: string) => void, onReindex?: (fileId: string) => void, onDelete?: (fileId: string) => void)}
  {#each node.folders as folder}
    <details class="knowledge-folder" open style={`--tree-depth: ${depth}`}>
      <summary>
        <span class="knowledge-folder-glyph" aria-hidden="true">/</span>
        <strong>{folder.name}</strong>
        <small>{countTree(folder)} file</small>
      </summary>
      <div class="knowledge-folder-children">
        {@render TreeView(folder, depth + 1, mode, onRemoveSelection, onReindex, onDelete)}
      </div>
    </details>
  {/each}
  {#each node.files as file}
    <article class="knowledge-item knowledge-tree-file" style={`--tree-depth: ${depth}`}>
      <span class="knowledge-file-glyph" aria-hidden="true">{extensionOf(file.path).replace(".", "").slice(0, 4) || "file"}</span>
      <div>
        <strong>{file.name}</strong>
        {#if mode === "selection"}
          <span>{file.path} - {formatBytes((file.item as File).size)}</span>
        {:else}
          <span>{(file.item as KnowledgeFile).status} - {formatBytes((file.item as KnowledgeFile).size_bytes)}{(file.item as KnowledgeFile).error ? ` - ${(file.item as KnowledgeFile).error}` : ""}</span>
        {/if}
      </div>
      <div class="inline-actions">
        {#if mode === "selection"}
          <Button size="sm" variant="ghost" disabled={busy} on:click={() => onRemoveSelection?.(file.path)}>Rimuovi</Button>
        {:else}
          <Button size="sm" variant="secondary" disabled={busy} on:click={() => onReindex?.((file.item as KnowledgeFile).id)}>Reindex</Button>
          <Button size="icon" variant="ghost" disabled={busy} on:click={() => onDelete?.((file.item as KnowledgeFile).id)} aria-label="Elimina file"><Trash2 size={15} /></Button>
        {/if}
      </div>
    </article>
  {/each}
{/snippet}
