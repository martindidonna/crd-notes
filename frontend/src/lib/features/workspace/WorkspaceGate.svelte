<script lang="ts">
  import { ArrowRight, Plus } from "lucide-svelte";
  import { Button } from "$lib/components/ui/button";
  import type { Workspace } from "$lib/api/types";

  export let workspaces: Workspace[] = [];
  export let activeWorkspaceId = "default";
  export let loading = false;
  export let message = "";
  export let onSelect: (workspaceId: string) => void;
  export let onCreate: (name: string) => Promise<void>;
  export let onEnter: () => void;

  let newWorkspaceName = "";

  async function create() {
    const name = newWorkspaceName.trim();
    if (!name) return;
    await onCreate(name);
    newWorkspaceName = "";
  }
</script>

<main class="workspace-gate-page">
  <section class="workspace-gate">
    <div class="brand gate-brand">
      <span class="brand-mark" aria-hidden="true">cn</span>
      <div>
        <p>Cardinal</p>
        <strong>notes</strong>
      </div>
    </div>

    <div>
      <p class="eyebrow">Accesso</p>
      <h1>Seleziona workspace</h1>
      <p class="muted">Il workspace definisce archivio, knowledge, chat e contesto operativo.</p>
    </div>

    <label>
      <span>Workspace attivo</span>
      <select value={activeWorkspaceId} on:change={(event) => onSelect(event.currentTarget.value)}>
        {#each workspaces as workspace}
          <option value={workspace.id}>{workspace.name}</option>
        {/each}
      </select>
    </label>

    <div class="workspace-create">
      <input
        bind:value={newWorkspaceName}
        type="text"
        placeholder="Nuovo workspace"
        on:keydown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            create();
          }
        }}
      />
      <Button size="icon" variant="secondary" on:click={create} aria-label="Crea workspace">
        <Plus size={17} />
      </Button>
    </div>

    {#if message}
      <p class="settings-note">{message}</p>
    {/if}

    <div class="form-actions">
      <Button disabled={loading || !activeWorkspaceId} on:click={onEnter}>
        <ArrowRight size={17} />
        Vai agli step
      </Button>
    </div>
  </section>
</main>
