<script lang="ts">
  import { Save } from "lucide-svelte";
  import { Button } from "$lib/components/ui/button";
  import type { Prompt } from "$lib/api/types";

  export let settings: Record<string, any> | null = null;
  export let prompts: Prompt[] = [];
  export let message = "";
  export let onSave: (settings: Record<string, any>) => Promise<void>;

  let tab: "transcription" | "summary" | "rag" = "transcription";
  let selectedConnector = "ollama";

  const providerLabels: Record<string, string> = {
    openai: "OpenAI",
    openrouter: "OpenRouter",
    ollama: "Ollama",
    lmstudio: "LM Studio",
    copilot: "GitHub Copilot"
  };

  const providerNeedsUrl = new Set(["ollama", "lmstudio"]);
  const providerNeedsKey = new Set(["openai", "openrouter"]);

  $: if (settings?.active_provider && !settings.providers?.[selectedConnector]) {
    selectedConnector = settings.active_provider as string;
  }
  $: provider = settings?.providers?.[selectedConnector] ?? {};
  $: rag = settings?.rag ?? {};

  function bool(value: unknown) {
    return String(Boolean(value));
  }

  function numberValue(value: FormDataEntryValue | null, fallback: number) {
    return Number(value || fallback);
  }

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    if (!settings) return;
    const form = new FormData(event.currentTarget as HTMLFormElement);
    const next = structuredClone(settings);

    if (tab === "transcription") {
      next.whisper_model = form.get("whisper_model");
      next.transcription_language = form.get("transcription_language");
      next.whisper_device = form.get("whisper_device");
      next.whisper_compute_type = form.get("whisper_compute_type");
      next.whisper_beam_size = numberValue(form.get("whisper_beam_size"), 1);
      next.whisper_cpu_threads = numberValue(form.get("whisper_cpu_threads"), 0);
      next.whisper_workers = numberValue(form.get("whisper_workers"), 1);
      next.whisper_vad_filter = form.get("whisper_vad_filter") === "true";
      next.whisper_condition_on_previous_text = form.get("whisper_condition_on_previous_text") === "true";
    }

    if (tab === "summary") {
      const name = selectedConnector;
      next.providers[name] = {
        enabled: form.get("provider.enabled") === "true",
        base_url: form.get("provider.base_url") || next.providers[name]?.base_url || "",
        model: form.get("provider.model") || "",
        api_key: form.get("provider.api_key") || ""
      };
      next.active_provider = form.get("active_provider") || name;
      next.active_prompt = form.get("active_prompt") || prompts[0]?.id || "";
    }

    if (tab === "rag") {
      next.rag = {
        enabled: form.get("rag.enabled") === "true",
        storage_dir: form.get("rag.storage_dir") || "rag",
        collection_prefix: form.get("rag.collection_prefix") || "workspace",
        embedding_model: form.get("rag.embedding_model") || "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        chunk_size_words: numberValue(form.get("rag.chunk_size_words"), 180),
        chunk_overlap_words: numberValue(form.get("rag.chunk_overlap_words"), 35),
        top_k: numberValue(form.get("rag.top_k"), 8),
        candidate_k: numberValue(form.get("rag.candidate_k"), 32),
        max_context_chars: numberValue(form.get("rag.max_context_chars"), 3200),
        hybrid_keyword_enabled: form.get("rag.hybrid_keyword_enabled") === "true",
        rerank_enabled: form.get("rag.rerank_enabled") === "true",
        rerank_model: form.get("rag.rerank_model") || "cross-encoder/ms-marco-MiniLM-L6-v2",
        enrich_summaries: form.get("rag.enrich_summaries") === "true",
        enrich_with_transcript_chunks: form.get("rag.enrich_with_transcript_chunks") === "true",
        enrich_with_summary_chunks: form.get("rag.enrich_with_summary_chunks") === "true",
        enrich_with_metadata_chunks: form.get("rag.enrich_with_metadata_chunks") === "true",
        enrich_with_operation_chunks: form.get("rag.enrich_with_operation_chunks") === "true",
        enrich_with_knowledge_chunks: form.get("rag.enrich_with_knowledge_chunks") === "true"
      };
    }

    await onSave(next);
  }
</script>

<section class="settings-panel">
  <div class="settings-tabs" role="tablist" aria-label="Sezioni settings">
    <button class:active={tab === "transcription"} class="settings-tab" type="button" on:click={() => (tab = "transcription")}>Trascrizione</button>
    <button class:active={tab === "summary"} class="settings-tab" type="button" on:click={() => (tab = "summary")}>AI summary</button>
    <button class:active={tab === "rag"} class="settings-tab" type="button" on:click={() => (tab = "rag")}>RAG</button>
  </div>

  {#if settings}
    <form class="settings-form" on:submit={submit}>
      {#if tab === "transcription"}
        <section class="settings-layout">
          <aside class="settings-context">
            <p class="eyebrow">Trascrizione</p>
            <h2>Whisper</h2>
            <p>Imposta velocita', accuratezza e consumo CPU della trascrizione locale.</p>
          </aside>
          <div class="settings-stack">
            <section class="settings-group">
              <div class="settings-group-title"><h3>Base</h3><p class="settings-note">Usa modelli piccoli per anteprime rapide, modelli grandi per revisioni finali.</p></div>
              <label><span>Modello Whisper</span><select name="whisper_model" value={settings.whisper_model}>{#each ["tiny", "base", "small", "medium", "large-v3"] as model}<option value={model}>{model}</option>{/each}</select></label>
              <label><span>Lingua trascrizione</span><input name="transcription_language" value={settings.transcription_language ?? ""} /></label>
              <label><span>Device Whisper</span><select name="whisper_device" value={settings.whisper_device ?? "cpu"}><option value="cpu">CPU</option><option value="cuda">CUDA</option></select></label>
              <label><span>Precisione Whisper</span><select name="whisper_compute_type" value={settings.whisper_compute_type}>{#each ["int8", "int8_float32", "float16", "float32"] as mode}<option value={mode}>{mode}</option>{/each}</select></label>
            </section>
            <section class="settings-group">
              <div class="settings-group-title"><h3>Prestazioni</h3><p class="settings-note">Beam size basso e filtro silenzi attivo riducono i tempi sugli audio lunghi.</p></div>
              <label><span>Beam size</span><input name="whisper_beam_size" type="number" min="1" max="8" value={settings.whisper_beam_size ?? 1} /></label>
              <label><span>Thread CPU</span><input name="whisper_cpu_threads" type="number" min="0" max="64" value={settings.whisper_cpu_threads ?? 0} /></label>
              <label><span>Worker Whisper</span><input name="whisper_workers" type="number" min="1" max="8" value={settings.whisper_workers ?? 1} /></label>
              <label><span>Filtro silenzi</span><select name="whisper_vad_filter" value={bool(settings.whisper_vad_filter)}><option value="true">Si</option><option value="false">No</option></select></label>
              <label><span>Contesto precedente</span><select name="whisper_condition_on_previous_text" value={bool(settings.whisper_condition_on_previous_text)}><option value="false">No</option><option value="true">Si</option></select></label>
            </section>
          </div>
        </section>
      {:else if tab === "summary"}
        <section class="settings-layout">
          <aside class="settings-context">
            <p class="eyebrow">AI summary</p>
            <h2>Connettore</h2>
            <p>Configura un connettore alla volta. Solo i connettori abilitati con modello scelto compaiono nel riassunto.</p>
          </aside>
          <div class="settings-stack">
            <section class="settings-group">
              <div class="settings-group-title"><h3>Connettore selezionato</h3><p class="settings-note">Configura URL, chiave e modello del provider.</p></div>
              <label class="wide"><span>Connettore disponibile</span><select bind:value={selectedConnector}>{#each Object.keys(settings.providers ?? {}) as name}<option value={name}>{providerLabels[name] ?? name}</option>{/each}</select></label>
              <label><span>Abilitato</span><select name="provider.enabled" value={bool(provider.enabled)}><option value="true">Si</option><option value="false">No</option></select></label>
              {#if providerNeedsUrl.has(selectedConnector)}
                <label><span>URL base</span><input name="provider.base_url" value={provider.base_url ?? ""} /></label>
              {:else}
                <input type="hidden" name="provider.base_url" value={provider.base_url ?? ""} />
              {/if}
              {#if providerNeedsKey.has(selectedConnector)}
                <label><span>Chiave API</span><input name="provider.api_key" type="password" value={provider.api_key ?? ""} /></label>
              {:else}
                <input type="hidden" name="provider.api_key" value="" />
              {/if}
              <label><span>Modello configurato</span><input name="provider.model" value={provider.model ?? ""} /></label>
            </section>
            <section class="settings-group">
              <div class="settings-group-title"><h3>Uso predefinito</h3><p class="settings-note">Queste scelte vengono usate come default nelle nuove sintesi.</p></div>
              <label><span>Provider attivo</span><select name="active_provider" value={settings.active_provider}>{#each Object.entries(settings.providers ?? {}).filter(([, item]) => (item as any).enabled) as [name]}<option value={name}>{providerLabels[name] ?? name}</option>{/each}</select></label>
              <label><span>Prompt predefinito</span><select name="active_prompt" value={settings.active_prompt}>{#each prompts as prompt}<option value={prompt.id}>{prompt.title}</option>{/each}</select></label>
            </section>
          </div>
        </section>
      {:else}
        <section class="settings-layout">
          <aside class="settings-context">
            <p class="eyebrow">RAG</p>
            <h2>Memoria workspace</h2>
            <p>Configura indicizzazione locale, retrieval e arricchimento dei riassunti con contesto storico.</p>
          </aside>
          <div class="settings-stack">
            <section class="settings-group">
              <div class="settings-group-title"><h3>Base</h3><p class="settings-note">Il vector DB resta locale. Ogni workspace ha una memoria separata.</p></div>
              <label><span>RAG abilitato</span><select name="rag.enabled" value={bool(rag.enabled)}><option value="true">Si</option><option value="false">No</option></select></label>
              <label><span>Directory storage</span><input name="rag.storage_dir" value={rag.storage_dir ?? "rag"} /></label>
              <label><span>Prefisso collection</span><input name="rag.collection_prefix" value={rag.collection_prefix ?? "workspace"} /></label>
              <label class="wide"><span>Embedding model</span><input name="rag.embedding_model" value={rag.embedding_model ?? "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"} /></label>
            </section>
            <section class="settings-group">
              <div class="settings-group-title"><h3>Retrieval</h3><p class="settings-note">Bilancia qualita', costo e tempi con chunking e top-k.</p></div>
              <label><span>Chunk size</span><input name="rag.chunk_size_words" type="number" min="40" max="500" value={rag.chunk_size_words ?? 180} /></label>
              <label><span>Chunk overlap</span><input name="rag.chunk_overlap_words" type="number" min="0" max="250" value={rag.chunk_overlap_words ?? 35} /></label>
              <label><span>Top K</span><input name="rag.top_k" type="number" min="1" max="20" value={rag.top_k ?? 8} /></label>
              <label><span>Candidati retrieval</span><input name="rag.candidate_k" type="number" min="8" max="80" value={rag.candidate_k ?? 32} /></label>
              <label><span>Max contesto</span><input name="rag.max_context_chars" type="number" min="800" max="12000" value={rag.max_context_chars ?? 3200} /></label>
              <label><span>Hybrid keyword search</span><select name="rag.hybrid_keyword_enabled" value={bool(rag.hybrid_keyword_enabled ?? true)}><option value="true">Si</option><option value="false">No</option></select></label>
              <label><span>Reranking locale</span><select name="rag.rerank_enabled" value={bool(rag.rerank_enabled ?? true)}><option value="true">Si</option><option value="false">No</option></select></label>
              <label class="wide"><span>Rerank model</span><input name="rag.rerank_model" value={rag.rerank_model ?? "cross-encoder/ms-marco-MiniLM-L6-v2"} /></label>
            </section>
            <section class="settings-group">
              <div class="settings-group-title"><h3>Arricchimento summary</h3><p class="settings-note">Seleziona quali sorgenti usare per il secondo passaggio di completamento.</p></div>
              {#each [
                ["rag.enrich_summaries", "Arricchisci i summary con RAG", rag.enrich_summaries],
                ["rag.enrich_with_transcript_chunks", "Usa trascrizioni", rag.enrich_with_transcript_chunks],
                ["rag.enrich_with_summary_chunks", "Usa summary storici", rag.enrich_with_summary_chunks],
                ["rag.enrich_with_metadata_chunks", "Usa metadati", rag.enrich_with_metadata_chunks],
                ["rag.enrich_with_operation_chunks", "Usa operativo", rag.enrich_with_operation_chunks],
                ["rag.enrich_with_knowledge_chunks", "Usa knowledge base file", rag.enrich_with_knowledge_chunks]
              ] as field}
                <label><span>{field[1]}</span><select name={field[0] as string} value={bool(field[2])}><option value="true">Si</option><option value="false">No</option></select></label>
              {/each}
            </section>
          </div>
        </section>
      {/if}

      <div class="settings-actions">
        {#if message}<p class="settings-note">{message}</p>{/if}
        <Button type="submit"><Save size={15} />Salva</Button>
      </div>
    </form>
  {:else}
    <p class="empty">Impostazioni non disponibili.</p>
  {/if}
</section>
