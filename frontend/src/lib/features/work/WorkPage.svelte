<script lang="ts">
  import { BookmarkPlus, Download, FileAudio, Mic, Pause, Play, Plus, Sparkles, Square, Trash2, X } from "lucide-svelte";
  import { Button } from "$lib/components/ui/button";
  import { Progress } from "$lib/components/ui/progress";
  import type { JobStatus, LibraryDetail, Prompt, RecordingMode, RecordingSession, RecordingSources } from "$lib/api/types";

  export let prompts: Prompt[] = [];
  export let job: JobStatus | null = null;
  export let currentDetail: LibraryDetail | null = null;
  export let recording: RecordingSession | null = null;
  export let recordingSources: RecordingSources | null = null;
  export let onUpload: (form: FormData) => Promise<void>;
  export let onSummary: (entryId: string, promptId: string) => Promise<void>;
  export let onRecordingStart: (payload: Record<string, unknown>) => Promise<void>;
  export let onRecordingPause: () => Promise<void>;
  export let onRecordingResume: () => Promise<void>;
  export let onRecordingBookmark: (label: string) => Promise<void>;
  export let onRecordingStop: (promptId: string) => Promise<void>;
  export let onRecordingCancel: () => Promise<void>;

  let file: File | null = null;
  let title = "";
  let recordedOn = new Date().toISOString().slice(0, 10);
  let notes = "";
  let participants = [""];
  let promptId = "";
  let acquisitionTab: "upload" | "recording" = "upload";
  let recordingMode: RecordingMode = "microphone_system";
  let microphoneDevice = "";
  let systemDevice = "";
  let windowHint = "";
  let bookmarkLabel = "";
  let hasSystemSource = false;

  $: if (!promptId && prompts.length) promptId = prompts[0].id;
  $: hasSystemSource = Boolean(recordingSources?.system.length);
  $: if (!hasSystemSource && ["microphone_system", "system"].includes(recordingMode)) recordingMode = "microphone";

  function selectFile(selected: File | null) {
    file = selected;
    if (file && !title) {
      title = file.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ");
      recordedOn = new Date(file.lastModified || Date.now()).toISOString().slice(0, 10);
    }
  }

  async function submit() {
    if (acquisitionTab !== "upload" || !file) return;
    const form = new FormData();
    form.set("file", file);
    form.set("title", title);
    form.set("recorded_on", recordedOn);
    form.set("notes", notes);
    form.set("participants", participants.map((item) => item.trim()).filter(Boolean).join(","));
    form.set("summarize", "false");
    await onUpload(form);
  }

  async function startBackendRecording() {
    await onRecordingStart({
      title,
      recorded_on: recordedOn || null,
      notes,
      participants: participants.map((item) => item.trim()).filter(Boolean),
      mode: recordingMode,
      microphone_device: microphoneDevice,
      system_device: systemDevice,
      window_hint: windowHint
    });
  }

  async function addBookmark() {
    await onRecordingBookmark(bookmarkLabel);
    bookmarkLabel = "";
  }

  function formatDuration(value = 0) {
    const total = Math.max(0, Math.floor(value));
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const seconds = total % 60;
    return hours
      ? `${hours.toString().padStart(2, "0")}:${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`
      : `${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
  }

  $: if (!microphoneDevice && recordingSources?.microphones.length) microphoneDevice = recordingSources.microphones[0].id;
  $: if (!systemDevice && recordingSources?.system.length) systemDevice = recordingSources.system[0].id;
</script>

<div class="process-grid">
  <section class="process-panel">
    <div class="panel-heading">
      <div>
        <span class="section-index">01</span>
        <p class="eyebrow">Trascrizione</p>
        <h2>Acquisizione</h2>
      </div>
      <div class="inline-actions">
        <a class:disabled={!currentDetail} class="secondary as-link" href={currentDetail ? `/api/library/${currentDetail.entry.id}/transcript.md` : "#"}>
          <Download size={15} />
          Trascrizione
        </a>
        <a class:disabled={!currentDetail?.summaries.length} class="secondary as-link" href={currentDetail ? `/api/library/${currentDetail.entry.id}/summary.md` : "#"}>
          <Download size={15} />
          Riassunto
        </a>
      </div>
    </div>

    <form class="stack-form" on:submit|preventDefault={submit}>
      <div class="form-grid">
        <label>
          <span>Titolo</span>
          <input bind:value={title} type="text" placeholder="Riunione prodotto" />
        </label>
        <label>
          <span>Data registrazione</span>
          <input bind:value={recordedOn} type="date" />
        </label>
        <label class="wide">
          <span>Note</span>
          <textarea bind:value={notes} rows="2" placeholder="Contesto utile per ritrovare la trascrizione"></textarea>
        </label>
      </div>

      <section class="sub-panel">
        <div class="inline-heading">
          <div>
            <p class="eyebrow">Opzionale</p>
            <h3>Partecipanti</h3>
          </div>
          <Button size="icon" variant="secondary" on:click={() => (participants = [...participants, ""])} aria-label="Aggiungi partecipante">
            <Plus size={16} />
          </Button>
        </div>
        <div class="participants-list">
          {#each participants as participant, index}
            <div class="participant-row">
              <input bind:value={participants[index]} type="text" placeholder="Nome partecipante" />
              <Button size="icon" variant="ghost" on:click={() => (participants = participants.filter((_, i) => i !== index))} aria-label="Rimuovi partecipante">
                <Trash2 size={15} />
              </Button>
            </div>
          {/each}
        </div>
      </section>

      <section class="acquisition-tabs">
        <div class="tab-list" role="tablist" aria-label="Modalita acquisizione">
          <button
            type="button"
            class:active={acquisitionTab === "upload"}
            role="tab"
            aria-selected={acquisitionTab === "upload"}
            on:click={() => (acquisitionTab = "upload")}
          >
            <FileAudio size={16} />
            Caricamento
          </button>
          <button
            type="button"
            class:active={acquisitionTab === "recording"}
            role="tab"
            aria-selected={acquisitionTab === "recording"}
            on:click={() => (acquisitionTab = "recording")}
          >
            <Mic size={16} />
            Ripresa live
          </button>
        </div>

        {#if acquisitionTab === "upload"}
          <div class="tab-panel" role="tabpanel">
            <label class="dropzone">
              <input type="file" accept="audio/*,video/*" on:change={(event) => selectFile(event.currentTarget.files?.[0] ?? null)} />
              <span class="dropzone-mark"><FileAudio size={18} /></span>
              <span>
                <strong>{file?.name ?? "Scegli o trascina file audio/video"}</strong>
                <small>Audio e video vengono convertiti automaticamente.</small>
              </span>
            </label>

            <div class="form-actions">
              <Button type="submit" disabled={!file}>Avvia trascrizione</Button>
            </div>
          </div>
        {:else}
          <div class="tab-panel recording-console" role="tabpanel">
            <div class="inline-heading">
              <div>
                <p class="eyebrow">Backend recorder</p>
                <h3>Registra ora</h3>
              </div>
              <div class="recording-clock" aria-live="polite">
                <span class:live={recording?.status === "recording"}></span>
                {formatDuration(recording?.elapsed_seconds ?? 0)}
              </div>
            </div>

            <div class="recording-grid">
              <label>
                <span>Sorgente</span>
                <select bind:value={recordingMode} disabled={!!recording}>
                  <option value="microphone_system" disabled={!hasSystemSource}>Microfono + Windows</option>
                  <option value="microphone">Solo microfono</option>
                  <option value="system" disabled={!hasSystemSource}>Solo Windows</option>
                  <option value="window" disabled={!recordingSources?.window_supported}>Finestra/app specifica</option>
                </select>
              </label>
              <label>
                <span>Microfono</span>
                <select bind:value={microphoneDevice} disabled={!!recording || recordingMode === "system"}>
                  {#if recordingSources?.microphones.length}
                    {#each recordingSources.microphones as source}
                      <option value={source.id}>{source.label}</option>
                    {/each}
                  {:else}
                    <option value="">Nessun device rilevato</option>
                  {/if}
                </select>
              </label>
              <label>
                <span>Audio Windows</span>
                <select bind:value={systemDevice} disabled={!!recording || recordingMode === "microphone"}>
                  {#if recordingSources?.system.length}
                    {#each recordingSources.system as source}
                      <option value={source.id}>{source.label}</option>
                    {/each}
                  {:else}
                    <option value="">Non disponibile</option>
                  {/if}
                </select>
              </label>
              <label>
                <span>Finestra/app</span>
                <input bind:value={windowHint} disabled={!!recording || recordingMode !== "window"} type="text" placeholder="Nome processo o finestra" />
              </label>
            </div>

            {#if (!hasSystemSource || recordingMode === "window") && recordingSources?.window_detail}
              <p class="recording-note">{recordingSources.window_detail}</p>
            {/if}

            <div class="recording-actions">
              {#if !recording}
                <Button type="button" variant="secondary" on:click={startBackendRecording} disabled={recordingMode !== "system" && !microphoneDevice}>
                  <Mic size={16} />
                  Registra
                </Button>
              {:else}
                {#if recording.status === "paused"}
                  <Button type="button" variant="secondary" on:click={onRecordingResume}>
                    <Play size={16} />
                    Riprendi
                  </Button>
                {:else}
                  <Button type="button" variant="secondary" on:click={onRecordingPause}>
                    <Pause size={16} />
                    Pausa
                  </Button>
                {/if}
                <Button type="button" on:click={() => onRecordingStop(promptId)}>
                  <Square size={16} />
                  Stop e trascrivi
                </Button>
                <Button type="button" variant="ghost" on:click={onRecordingCancel} aria-label="Annulla registrazione">
                  <X size={16} />
                </Button>
              {/if}
            </div>

            {#if recording}
              <div class="bookmark-row">
                <input bind:value={bookmarkLabel} type="text" placeholder="Etichetta segnalibro" on:keydown={(event) => { if (event.key === "Enter") { event.preventDefault(); addBookmark(); } }} />
                <Button type="button" variant="secondary" on:click={addBookmark}>
                  <BookmarkPlus size={16} />
                  Segna
                </Button>
              </div>
              {#if recording.bookmarks.length}
                <div class="bookmark-list">
                  {#each recording.bookmarks as bookmark}
                    <span>{formatDuration(bookmark.timestamp_seconds)} - {bookmark.label}</span>
                  {/each}
                </div>
              {/if}
            {/if}
          </div>
        {/if}
      </section>

      <section class="process-status">
        <div class="status-copy">
          <strong>{job?.status ?? "Pronto"}</strong>
          <span>{job?.message ?? "In attesa di un file o di una registrazione."}</span>
        </div>
        <Progress value={job?.progress ?? 0} />
        {#if job?.error}
          <pre class="error-text">{job.error}</pre>
        {/if}
      </section>
    </form>

    <section class="document-pane">
      <div class="document-head">
        <div>
          <p class="eyebrow">Trascrizione corrente</p>
          <h3>{currentDetail?.entry.title ?? "Nessuna trascrizione selezionata"}</h3>
        </div>
      </div>
      <div class="text-surface fixed-text muted">{currentDetail?.entry.transcript ?? "La trascrizione comparira' qui dopo l'elaborazione."}</div>
    </section>
  </section>

  <section class="process-panel">
    <div class="panel-heading">
      <div>
        <span class="section-index">02</span>
        <p class="eyebrow">Riassunto</p>
        <h2>Prompt e output</h2>
      </div>
      <Button disabled={!currentDetail} on:click={() => currentDetail && onSummary(currentDetail.entry.id, promptId)}>
        <Sparkles size={16} />
        Genera
      </Button>
    </div>

    <label>
      <span>Prompt</span>
      <select bind:value={promptId}>
        {#each prompts as prompt}
          <option value={prompt.id}>{prompt.title}</option>
        {/each}
      </select>
    </label>

    <section class="document-pane">
      <div class="document-head">
        <div>
          <p class="eyebrow">Output AI</p>
          <h3>Riassunto</h3>
        </div>
      </div>
      <div class="text-surface fixed-text muted">
        {currentDetail?.summaries[0]?.content ?? "Nessun riassunto disponibile."}
      </div>
    </section>
  </section>
</div>
