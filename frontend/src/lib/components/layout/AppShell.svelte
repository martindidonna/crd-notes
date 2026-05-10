<script lang="ts">
  import {
    Archive,
    Bot,
    Boxes,
    Brain,
    CheckSquare,
    Settings,
    UploadCloud
  } from "lucide-svelte";
  import {
    activePage,
    activeWorkspaceId,
    hasEnteredWorkspace,
    workspaces,
    type AppPage
  } from "$lib/stores/app-state";

  const pages: Array<{ id: AppPage; label: string; icon: typeof UploadCloud }> = [
    { id: "work", label: "Lavoro", icon: UploadCloud },
    { id: "operations", label: "Operativo", icon: CheckSquare },
    { id: "knowledge", label: "Knowledge", icon: Boxes },
    { id: "intelligence", label: "Contesto", icon: Brain },
    { id: "chat", label: "Cardinal", icon: Bot },
    { id: "library", label: "Archivio", icon: Archive },
    { id: "settings", label: "Setup", icon: Settings }
  ];

  $: activeWorkspace = $workspaces.find((item) => item.id === $activeWorkspaceId);
</script>

<div class="app-frame">
  <aside class="side-rail">
    <div class="brand">
      <span class="brand-mark" aria-hidden="true">cn</span>
      <div>
        <p>Cardinal</p>
        <strong>notes</strong>
      </div>
    </div>

    <nav class="page-nav" aria-label="Navigazione principale">
      {#each pages as page, index}
        <button
          type="button"
          class="ui-button nav-button"
          class:ui-button-secondary={$activePage === page.id}
          class:ui-button-ghost={$activePage !== page.id}
          aria-current={$activePage === page.id ? "page" : undefined}
          on:click={() => activePage.set(page.id)}
        >
          <span>{String(index + 1).padStart(2, "0")}</span>
          <svelte:component this={page.icon} size={17} strokeWidth={1.8} />
          <strong>{page.label}</strong>
        </button>
      {/each}
    </nav>
  </aside>

  <main class="workspace">
    <header class="topbar">
      <div>
        <button class="workspace-pill" type="button" on:click={() => hasEnteredWorkspace.set(false)}>
          <span aria-hidden="true">&larr;</span>
          <span>Workspace attivo</span>
          <strong>{activeWorkspace?.name ?? "Generico"}</strong>
        </button>
        <p class="eyebrow">Cardinal notes</p>
        <h1>{pages.find((item) => item.id === $activePage)?.label ?? "Workspace"}</h1>
      </div>
    </header>

    <slot />
  </main>
</div>
