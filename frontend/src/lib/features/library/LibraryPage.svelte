<script lang="ts">
  import { Download, ListChecks, Sparkles } from "lucide-svelte";
  import { Button } from "$lib/components/ui/button";
  import type { LibraryDetail, LibraryEntry, Prompt } from "$lib/api/types";

  export let entries: LibraryEntry[] = [];
  export let detail: LibraryDetail | null = null;
  export let prompts: Prompt[] = [];
  export let filters = {
    q: "",
    participant: "all",
    keyword: "",
    date_from: "",
    date_to: "",
    summary_filter: "all"
  };
  export let onFilter: (filters: typeof filters) => void;
  export let onSelect: (entryId: string) => Promise<void>;
  export let onSummary: (entryId: string, promptId: string) => Promise<void>;
  export let onExtractOperations: (entryId: string, ai: boolean) => Promise<void>;

  let promptId = "";
  $: if (!promptId && prompts.length) promptId = prompts[0].id;
  $: participants = Array.from(new Set(entries.flatMap((entry) => entry.participants))).sort();

  function updateFilters(next: Partial<typeof filters>) {
    onFilter({ ...filters, ...next });
  }
</script>

<section class="library-layout">
  <section class="library-filters">
    <label class="library-search-field">
      <span>Cerca archivio</span>
      <input value={filters.q} type="search" placeholder="Titolo, note, partecipante, testo" on:input={(event) => updateFilters({ q: event.currentTarget.value })} />
    </label>
    <label>
      <span>Persona</span>
      <select value={filters.participant} on:change={(event) => updateFilters({ participant: event.currentTarget.value })}>
        <option value="all">Tutti</option>
        {#each participants as participant}
          <option value={participant}>{participant}</option>
        {/each}
      </select>
    </label>
    <label>
      <span>Parola chiave</span>
      <input value={filters.keyword} type="search" placeholder="Tag, keyword, tema" on:input={(event) => updateFilters({ keyword: event.currentTarget.value })} />
    </label>
    <label>
      <span>Dal</span>
      <input value={filters.date_from} type="date" on:change={(event) => updateFilters({ date_from: event.currentTarget.value })} />
    </label>
    <label>
      <span>Al</span>
      <input value={filters.date_to} type="date" on:change={(event) => updateFilters({ date_to: event.currentTarget.value })} />
    </label>
    <label>
      <span>Riassunto</span>
      <select value={filters.summary_filter} on:change={(event) => updateFilters({ summary_filter: event.currentTarget.value })}>
        <option value="all">Tutti</option>
        <option value="with">Con riassunto</option>
        <option value="without">Senza riassunto</option>
      </select>
    </label>
  </section>

  <div class="library-browser">
    <aside class="library-index">
      <div class="library-list-head">
        <div>
          <p class="eyebrow">Note</p>
          <h2>Risultati</h2>
        </div>
        <span class="counter">{entries.length}</span>
      </div>
      <div class="library-list">
        {#if entries.length === 0}
          <p class="empty">Nessuna trascrizione disponibile nel workspace corrente.</p>
        {:else}
          {#each entries as entry}
            <button class:active={detail?.entry.id === entry.id} class="entry-button" type="button" on:click={() => onSelect(entry.id)}>
              <strong>{entry.title}</strong>
              <span>{entry.source_filename}</span>
              <small>{entry.summary_count} summary · {entry.operation_open_count}/{entry.operation_total_count} operativi aperti</small>
            </button>
          {/each}
        {/if}
      </div>
    </aside>

    <section class="library-detail-panel">
      <div class="detail-header">
        <div>
          <p class="eyebrow">Dettaglio</p>
          <h2>{detail?.entry.title ?? "Seleziona una trascrizione"}</h2>
        </div>
        <div class="inline-actions">
          <a class:disabled={!detail} class="secondary as-link" href={detail ? `/api/library/${detail.entry.id}/transcript.md` : "#"}>
            <Download size={15} />
            Trascrizione
          </a>
          <a class:disabled={!detail?.summaries.length} class="secondary as-link" href={detail ? `/api/library/${detail.entry.id}/summary.md` : "#"}>
            <Download size={15} />
            Riassunto
          </a>
        </div>
      </div>

      <div class="library-detail-grid">
        <article class="document-pane">
          <div class="document-head"><h3>Trascrizione</h3></div>
          <div class="text-surface fixed-text muted">{detail?.entry.transcript ?? "Nessun elemento selezionato."}</div>
        </article>

        <article class="document-pane">
          <div class="document-head">
            <div>
              <p class="eyebrow">Completamento</p>
              <h3>Riassunti</h3>
            </div>
            <div class="inline-actions">
              <Button size="sm" variant="secondary" disabled={!detail?.summaries.length} on:click={() => detail && onExtractOperations(detail.entry.id, false)}>
                <ListChecks size={15} />
                Importa operativo
              </Button>
              <Button size="sm" variant="secondary" disabled={!detail?.summaries.length} on:click={() => detail && onExtractOperations(detail.entry.id, true)}>
                <Sparkles size={15} />
                Migliora con AI
              </Button>
            </div>
          </div>
          <div class="summary-selects">
            <label>
              <span>Prompt</span>
              <select bind:value={promptId}>
                {#each prompts as prompt}
                  <option value={prompt.id}>{prompt.title}</option>
                {/each}
              </select>
            </label>
            <Button disabled={!detail} on:click={() => detail && onSummary(detail.entry.id, promptId)}>
              <Sparkles size={15} />
              Genera riassunto
            </Button>
          </div>
          <div class="text-surface fixed-text muted">{detail?.summaries[0]?.content ?? "Nessun elemento selezionato."}</div>
        </article>
      </div>
    </section>
  </div>
</section>
