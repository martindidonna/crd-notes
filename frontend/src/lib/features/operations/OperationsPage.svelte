<script lang="ts">
  import { Trash2 } from "lucide-svelte";
  import { Button } from "$lib/components/ui/button";
  import type { OperationItem } from "$lib/api/types";

  export let operations: OperationItem[] = [];
  export let onPatch: (itemId: string, payload: Partial<OperationItem>) => Promise<void>;
  export let onDelete: (itemId: string) => Promise<void>;
  let q = "";
  let kind = "all";
  let status = "all";
  const labels: Record<string, string> = { action: "Azioni", decision: "Decisioni", risk: "Rischi", question: "Domande" };
  $: filtered = operations.filter((item) => {
    const text = `${item.text} ${item.owner} ${item.entry?.title ?? ""}`.toLowerCase();
    return (!q || text.includes(q.toLowerCase())) && (kind === "all" || item.kind === kind) && (status === "all" || item.status === status);
  });
</script>

<section class="operations-panel">
  <div class="operations-toolbar">
    <label><span>Cerca</span><input bind:value={q} type="search" placeholder="Testo, owner, trascrizione" /></label>
    <label><span>Tipo</span><select bind:value={kind}><option value="all">Tutti</option><option value="action">Azioni</option><option value="decision">Decisioni</option><option value="risk">Rischi</option><option value="question">Domande</option></select></label>
    <label><span>Stato</span><select bind:value={status}><option value="all">Tutti</option><option value="open">Aperti</option><option value="done">Completati</option></select></label>
  </div>

  <div class="operations-summary">
    {#each ["action", "decision", "risk", "question"] as itemKind}
      <article class="mini-stat"><strong>{operations.filter((item) => item.kind === itemKind).length}</strong><span>{labels[itemKind]}</span></article>
    {/each}
  </div>

  <div class="operations-board">
    {#each filtered as item}
      <article class="operation-card">
        <div>
          <p class="eyebrow">{labels[item.kind] ?? item.kind}</p>
          <h3>{item.text}</h3>
          <p class="muted">{item.entry?.title ?? "Origine non disponibile"}</p>
        </div>
        <div class="operation-fields">
          <input value={item.owner} placeholder="Owner" on:change={(event) => onPatch(item.id, { owner: event.currentTarget.value } as Partial<OperationItem>)} />
          <input value={item.due_date ?? ""} type="date" on:change={(event) => onPatch(item.id, { due_date: event.currentTarget.value || null } as Partial<OperationItem>)} />
          <select value={item.status} on:change={(event) => onPatch(item.id, { status: event.currentTarget.value } as Partial<OperationItem>)}>
            <option value="open">Aperto</option>
            <option value="done">Completato</option>
          </select>
          <Button size="icon" variant="ghost" on:click={() => onDelete(item.id)} aria-label="Elimina elemento">
            <Trash2 size={15} />
          </Button>
        </div>
      </article>
    {/each}
  </div>
</section>
