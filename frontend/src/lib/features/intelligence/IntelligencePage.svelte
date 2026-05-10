<script lang="ts">
  import { Sparkles } from "lucide-svelte";
  import { Button } from "$lib/components/ui/button";
  import type { WorkspaceIntelligence } from "$lib/api/types";

  export let intelligence: WorkspaceIntelligence | null = null;
  export let aiBrief = "";
  export let onAiBrief: () => Promise<void>;
</script>

<section class="intelligence-layout">
  <section class="process-panel">
    <div class="section-heading-line">
      <div>
        <p class="eyebrow">Workspace intelligence</p>
        <h2>Contesto attivo</h2>
      </div>
      <Button variant="secondary" on:click={onAiBrief}><Sparkles size={15} />Aggiorna brief estratto</Button>
    </div>
    <p class="intelligence-copy">{aiBrief || intelligence?.local_brief || "Nessun dato disponibile."}</p>
    <div class="operations-summary">
      <article class="mini-stat"><strong>{intelligence?.entry_count ?? 0}</strong><span>Trascrizioni</span></article>
      <article class="mini-stat"><strong>{intelligence?.summary_count ?? 0}</strong><span>Riassunti</span></article>
      <article class="mini-stat"><strong>{intelligence?.operation_open_count ?? 0}</strong><span>Operativi aperti</span></article>
    </div>
  </section>

  <section class="process-panel">
    <p class="eyebrow">Raggruppamenti ML</p>
    <h2>Cluster ricorrenti</h2>
    <div class="cluster-list">
      {#each intelligence?.clusters ?? [] as cluster}
        <article class="cluster-card"><strong>{cluster.title}</strong><span>{cluster.terms.join(", ")}</span></article>
      {/each}
    </div>
  </section>
</section>
