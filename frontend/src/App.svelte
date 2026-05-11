<script lang="ts">
  import { onMount } from "svelte";
  import AppShell from "$lib/components/layout/AppShell.svelte";
  import {
    createChatThread,
    createJob,
    createWorkspaceBrief,
    addRecordingBookmark,
    cancelCopilotLogin,
    cancelRecording,
    deleteChatThread,
    deleteKnowledgeFile,
    deleteOperation,
    getJob,
    getSettings,
    getWorkspaceIntelligence,
    listProviderModels,
    listChatThreads,
    listKnowledgeFiles,
    listOperations,
    listPrompts,
    listRecordingSources,
    patchOperation,
    pauseRecording,
    readChatThread,
    readCopilotLoginStatus,
    readRecording,
    reindexKnowledge,
    reindexKnowledgeFile,
    resumeRecording,
    saveSettings,
    sendChatMessage,
    startCopilotLogin,
    startRecording,
    stopRecording,
    testProviderModels,
    uploadKnowledgeFiles
  } from "$lib/api/app";
  import {
    createSummaryStream,
    extractOperations,
    getLibraryDetail,
    listLibrary,
    type LibraryFilters
  } from "$lib/api/library";
  import { createWorkspace, listWorkspaces } from "$lib/api/workspaces";
  import ChatPage from "$lib/features/chat/ChatPage.svelte";
  import IntelligencePage from "$lib/features/intelligence/IntelligencePage.svelte";
  import KnowledgePage from "$lib/features/knowledge/KnowledgePage.svelte";
  import LibraryPage from "$lib/features/library/LibraryPage.svelte";
  import OperationsPage from "$lib/features/operations/OperationsPage.svelte";
  import SettingsPage from "$lib/features/settings/SettingsPage.svelte";
  import WorkPage from "$lib/features/work/WorkPage.svelte";
  import WorkspaceGate from "$lib/features/workspace/WorkspaceGate.svelte";
  import {
    activePage,
    activeWorkspaceId,
    appError,
    appLoading,
    hasEnteredWorkspace,
    knowledgeFiles,
    libraryEntries,
    operations,
    prompts,
    workspaceIntelligence,
    workspaces
  } from "$lib/stores/app-state";
  import type { ChatMessage, ChatThread, JobStatus, LibraryDetail, OperationItem, ProviderModelsResponse, RecordingSession, RecordingSources } from "$lib/api/types";

  let currentDetail: LibraryDetail | null = null;
  let currentJob: JobStatus | null = null;
  let currentRecording: RecordingSession | null = null;
  let recordingSources: RecordingSources | null = null;
  let recordingPollTimer: ReturnType<typeof setInterval> | null = null;
  let libraryFilters: LibraryFilters = { summary_filter: "all" };
  let chatThreads: ChatThread[] = [];
  let chatMessages: ChatMessage[] = [];
  let activeChatThreadId = "";
  let chatLoading = false;
  let currentSettings: Record<string, unknown> | null = null;
  let providerModels: Record<string, string[]> = {};
  let settingsMessage = "";
  let workspaceMessage = "";
  let knowledgeMessage = "";
  let aiBrief = "";
  let loadedWorkspaceId = "";
  let uploadLoading = false;
  let summaryLoading = false;
  let summaryDraft = "";
  let summaryStatus = "";

  function showError(error: unknown) {
    appError.set(error instanceof Error ? error.message : "Operazione non riuscita.");
  }

  function hydrateProviderModels(settings: Record<string, unknown> | null) {
    const providers = (settings?.providers ?? {}) as Record<string, { available_models?: string[]; model?: string }>;
    providerModels = Object.fromEntries(
      Object.entries(providers).map(([name, provider]) => [
        name,
        Array.from(new Set([...(provider.available_models ?? []), provider.model].filter(Boolean) as string[]))
      ])
    );
  }

  async function saveProviderModelCache(provider: string, response: ProviderModelsResponse) {
    const models = Array.from(new Set(response.models));
    if (response.source === "error" && models.length === 0) return;
    providerModels = { ...providerModels, [provider]: models };
    if (!currentSettings) return;

    const nextSettings = structuredClone(currentSettings) as Record<string, any>;
    const target = nextSettings.providers?.[provider];
    if (!target) return;

    target.available_models = models;
    if (!target.model && models.length) {
      target.model = models[0];
    }
    const saved = await saveSettings(nextSettings);
    currentSettings = saved.settings;
    hydrateProviderModels(currentSettings);
  }

  async function loadInitialData() {
    appLoading.set(true);
    appError.set("");
    try {
      const [loadedWorkspaces, loadedPrompts, settings] = await Promise.all([
        listWorkspaces(),
        listPrompts(),
        getSettings()
      ]);
      workspaces.set(loadedWorkspaces);
      prompts.set(loadedPrompts);
      currentSettings = settings.settings;
      hydrateProviderModels(currentSettings);
      recordingSources = await listRecordingSources().catch(() => ({
        microphones: [],
        system: [],
        window_supported: false,
        window_detail: "Sorgenti backend non rilevate. Verifica ffmpeg e i permessi audio di Windows."
      }));
      const saved = localStorage.getItem("crd-notes-workspace");
      const selected = loadedWorkspaces.find((item) => item.id === saved) ?? loadedWorkspaces.find((item) => item.is_default) ?? loadedWorkspaces[0];
      activeWorkspaceId.set(selected?.id ?? "default");
    } catch (error) {
      showError(error);
    } finally {
      appLoading.set(false);
    }
  }

  async function refreshWorkspaceData(workspaceId: string) {
    if (!workspaceId) return;
    try {
      const [entries, ops, knowledge, intelligence, threads] = await Promise.all([
        listLibrary(workspaceId, libraryFilters),
        listOperations(workspaceId),
        listKnowledgeFiles(workspaceId),
        getWorkspaceIntelligence(workspaceId),
        listChatThreads(workspaceId)
      ]);
      libraryEntries.set(entries);
      operations.set(ops);
      knowledgeFiles.set(knowledge);
      workspaceIntelligence.set(intelligence);
      chatThreads = threads;
      loadedWorkspaceId = workspaceId;
      if (currentDetail && !entries.some((entry) => entry.id === currentDetail?.entry.id)) {
        currentDetail = null;
      }
    } catch (error) {
      showError(error);
    }
  }

  async function enterWorkspace() {
    hasEnteredWorkspace.set(true);
    await refreshWorkspaceData($activeWorkspaceId);
  }

  async function addWorkspace(name: string) {
    try {
      const workspace = await createWorkspace(name);
      const loaded = await listWorkspaces();
      workspaces.set(loaded);
      activeWorkspaceId.set(workspace.id);
      workspaceMessage = "Workspace creato.";
    } catch (error) {
      showError(error);
    }
  }

  async function selectWorkspace(workspaceId: string) {
    activeWorkspaceId.set(workspaceId);
    localStorage.setItem("crd-notes-workspace", workspaceId);
    currentDetail = null;
    currentJob = null;
    aiBrief = "";
    await refreshWorkspaceData(workspaceId);
  }

  async function uploadMedia(form: FormData) {
    try {
      uploadLoading = true;
      form.set("workspace_id", $activeWorkspaceId);
      const response = await createJob(form);
      currentJob = { id: response.job_id, status: "running", stage: "upload", progress: 5, message: "File inviato.", error: null, entry_id: null, created_at: "", updated_at: "" };
      await pollJob(response.job_id);
    } catch (error) {
      showError(error);
    } finally {
      uploadLoading = false;
    }
  }

  async function beginRecording(payload: Record<string, unknown>) {
    try {
      currentRecording = await startRecording({ ...payload, workspace_id: $activeWorkspaceId });
    } catch (error) {
      showError(error);
    }
  }

  async function pauseCurrentRecording() {
    if (!currentRecording) return;
    try {
      currentRecording = await pauseRecording(currentRecording.id);
    } catch (error) {
      showError(error);
    }
  }

  async function resumeCurrentRecording() {
    if (!currentRecording) return;
    try {
      currentRecording = await resumeRecording(currentRecording.id);
    } catch (error) {
      showError(error);
    }
  }

  async function bookmarkCurrentRecording(label: string) {
    if (!currentRecording) return;
    try {
      currentRecording = await addRecordingBookmark(currentRecording.id, label);
    } catch (error) {
      showError(error);
    }
  }

  async function stopCurrentRecording(promptId: string) {
    if (!currentRecording) return;
    try {
      const response = await stopRecording(currentRecording.id, promptId);
      currentRecording = null;
      currentJob = { id: response.job_id, status: "running", stage: "recording", progress: 5, message: "Registrazione salvata.", error: null, entry_id: null, created_at: "", updated_at: "" };
      await pollJob(response.job_id);
    } catch (error) {
      showError(error);
    }
  }

  async function cancelCurrentRecording() {
    if (!currentRecording) return;
    try {
      await cancelRecording(currentRecording.id);
      currentRecording = null;
    } catch (error) {
      showError(error);
    }
  }

  async function pollJob(jobId: string) {
    for (;;) {
      await new Promise((resolve) => setTimeout(resolve, 1200));
      currentJob = await getJob(jobId);
      if (["completed", "failed", "cancelled"].includes(currentJob.status)) break;
    }
    await refreshWorkspaceData($activeWorkspaceId);
    if (currentJob.entry_id) {
      currentDetail = await getLibraryDetail(currentJob.entry_id);
    }
  }

  async function selectEntry(entryId: string) {
    try {
      currentDetail = await getLibraryDetail(entryId);
    } catch (error) {
      showError(error);
    }
  }

  async function generateSummary(entryId: string, promptId: string, provider = "", model = "") {
    try {
      summaryLoading = true;
      summaryDraft = "";
      summaryStatus = "Connessione al modello AI.";
      await createSummaryStream(entryId, promptId, model, provider, (event) => {
        if (event.type === "status") {
          summaryStatus = event.message;
        }
        if (event.type === "delta") {
          summaryDraft += event.content;
        }
        if (event.type === "replace") {
          summaryDraft = event.content;
          summaryStatus = "Riassunto arricchito con il contesto.";
        }
        if (event.type === "done") {
          summaryDraft = event.summary.content;
          summaryStatus = "Riassunto salvato.";
        }
      });
      currentDetail = await getLibraryDetail(entryId);
      await refreshWorkspaceData($activeWorkspaceId);
    } catch (error) {
      showError(error);
    } finally {
      summaryLoading = false;
      summaryStatus = "";
    }
  }

  async function runOperationExtract(entryId: string, ai: boolean) {
    try {
      await extractOperations(entryId, ai);
      await refreshWorkspaceData($activeWorkspaceId);
    } catch (error) {
      showError(error);
    }
  }

  async function updateOperation(itemId: string, payload: Partial<OperationItem>) {
    try {
      await patchOperation(itemId, payload);
      operations.set(await listOperations($activeWorkspaceId));
    } catch (error) {
      showError(error);
    }
  }

  async function removeOperation(itemId: string) {
    try {
      await deleteOperation(itemId);
      operations.set(await listOperations($activeWorkspaceId));
    } catch (error) {
      showError(error);
    }
  }

  async function uploadKnowledge(selected: File[]) {
    try {
      knowledgeMessage = "Upload knowledge in corso.";
      await uploadKnowledgeFiles($activeWorkspaceId, selected);
      knowledgeFiles.set(await listKnowledgeFiles($activeWorkspaceId));
      knowledgeMessage = "Knowledge aggiornata.";
    } catch (error) {
      knowledgeMessage = "";
      showError(error);
    }
  }

  async function refreshAiBrief() {
    try {
      aiBrief = (await createWorkspaceBrief($activeWorkspaceId)).brief;
    } catch (error) {
      showError(error);
    }
  }

  async function newChatThread() {
    const thread = await createChatThread($activeWorkspaceId);
    chatThreads = await listChatThreads($activeWorkspaceId);
    activeChatThreadId = thread.id;
    chatMessages = [];
  }

  async function openChatThread(threadId: string) {
    const detail = await readChatThread($activeWorkspaceId, threadId);
    activeChatThreadId = detail.thread.id;
    chatMessages = detail.messages;
  }

  async function removeChatThread(threadId: string) {
    await deleteChatThread($activeWorkspaceId, threadId);
    chatThreads = await listChatThreads($activeWorkspaceId);
    if (activeChatThreadId === threadId) {
      activeChatThreadId = "";
      chatMessages = [];
    }
  }

  async function postChat(content: string) {
    try {
      chatLoading = true;
      const response = await sendChatMessage($activeWorkspaceId, activeChatThreadId || "new", content);
      activeChatThreadId = response.thread.id;
      chatMessages = [...chatMessages, ...response.messages];
      chatThreads = await listChatThreads($activeWorkspaceId);
    } catch (error) {
      showError(error);
    } finally {
      chatLoading = false;
    }
  }

  async function persistSettings(nextSettings: Record<string, unknown>) {
    try {
      const saved = await saveSettings(nextSettings);
      currentSettings = saved.settings;
      hydrateProviderModels(currentSettings);
      settingsMessage = "Impostazioni salvate.";
    } catch (error) {
      showError(error);
    }
  }

  async function importProviderModels(provider: string) {
    const response = await listProviderModels(provider);
    await saveProviderModelCache(provider, response);
    return response;
  }

  async function testProvider(provider: string, providerSettings: any) {
    const response = await testProviderModels(provider, providerSettings);
    await saveProviderModelCache(provider, response);
    return response;
  }

  async function loginCopilot() {
    return startCopilotLogin();
  }

  async function stopCopilotLogin() {
    return cancelCopilotLogin();
  }

  async function getCopilotLogin() {
    const response = await readCopilotLoginStatus();
    if (response.models?.length) {
      await saveProviderModelCache("copilot", {
        provider: "copilot",
        models: response.models,
        source: "remote",
        message: response.message ?? ""
      });
    }
    return response;
  }

  onMount(loadInitialData);

  $: {
    const shouldPoll = currentRecording?.id && ["recording", "paused"].includes(currentRecording.status);
    if (shouldPoll && !recordingPollTimer) {
      recordingPollTimer = setInterval(async () => {
        if (!currentRecording?.id) return;
        try {
          currentRecording = await readRecording(currentRecording.id);
        } catch {
          if (recordingPollTimer) clearInterval(recordingPollTimer);
          recordingPollTimer = null;
        }
      }, 1000);
    }
    if (!shouldPoll && recordingPollTimer) {
      clearInterval(recordingPollTimer);
      recordingPollTimer = null;
    }
  }

  $: if ($hasEnteredWorkspace && $activeWorkspaceId) {
    if (loadedWorkspaceId !== $activeWorkspaceId) {
      refreshWorkspaceData($activeWorkspaceId);
    }
  }
</script>

{#if !$hasEnteredWorkspace}
  <WorkspaceGate
    workspaces={$workspaces}
    activeWorkspaceId={$activeWorkspaceId}
    loading={$appLoading}
    message={workspaceMessage}
    onSelect={selectWorkspace}
    onCreate={addWorkspace}
    onEnter={enterWorkspace}
  />
{:else}
  <AppShell>
    {#if $appError}
      <div class="notice" role="alert">{$appError}</div>
    {/if}

    {#if $appLoading}
      <section class="process-panel"><p class="muted">Caricamento workspace...</p></section>
    {:else if $activePage === "work"}
      <WorkPage
        prompts={$prompts}
        job={currentJob}
        currentDetail={currentDetail}
        recording={currentRecording}
        recordingSources={recordingSources}
        settings={currentSettings}
        providerModels={providerModels}
        onUpload={uploadMedia}
        onSummary={generateSummary}
        uploadLoading={uploadLoading}
        summaryLoading={summaryLoading}
        summaryDraft={summaryDraft}
        summaryStatus={summaryStatus}
        onRecordingStart={beginRecording}
        onRecordingPause={pauseCurrentRecording}
        onRecordingResume={resumeCurrentRecording}
        onRecordingBookmark={bookmarkCurrentRecording}
        onRecordingStop={stopCurrentRecording}
        onRecordingCancel={cancelCurrentRecording}
      />
    {:else if $activePage === "library"}
      <LibraryPage
        entries={$libraryEntries}
        detail={currentDetail}
        prompts={$prompts}
        settings={currentSettings}
        providerModels={providerModels}
        filters={libraryFilters}
        onFilter={(filters) => { libraryFilters = filters; refreshWorkspaceData($activeWorkspaceId); }}
        onSelect={selectEntry}
        onSummary={generateSummary}
        summaryLoading={summaryLoading}
        summaryDraft={summaryDraft}
        summaryStatus={summaryStatus}
        onExtractOperations={runOperationExtract}
      />
    {:else if $activePage === "operations"}
      <OperationsPage operations={$operations} onPatch={updateOperation} onDelete={removeOperation} />
    {:else if $activePage === "knowledge"}
      <KnowledgePage
        files={$knowledgeFiles}
        message={knowledgeMessage}
        onUpload={uploadKnowledge}
        onReindexAll={async () => { await reindexKnowledge($activeWorkspaceId); knowledgeFiles.set(await listKnowledgeFiles($activeWorkspaceId)); }}
        onReindexFile={async (fileId) => { await reindexKnowledgeFile($activeWorkspaceId, fileId); knowledgeFiles.set(await listKnowledgeFiles($activeWorkspaceId)); }}
        onDeleteFile={async (fileId) => { await deleteKnowledgeFile($activeWorkspaceId, fileId); knowledgeFiles.set(await listKnowledgeFiles($activeWorkspaceId)); }}
      />
    {:else if $activePage === "intelligence"}
      <IntelligencePage intelligence={$workspaceIntelligence} aiBrief={aiBrief} onAiBrief={refreshAiBrief} />
    {:else if $activePage === "chat"}
      <ChatPage
        threads={chatThreads}
        activeThreadId={activeChatThreadId}
        messages={chatMessages}
        loading={chatLoading}
        onNewThread={newChatThread}
        onSelectThread={openChatThread}
        onDeleteThread={removeChatThread}
        onSend={postChat}
      />
    {:else}
      <SettingsPage
        settings={currentSettings}
        prompts={$prompts}
        message={settingsMessage}
        providerModels={providerModels}
        onSave={persistSettings}
        onImportModels={importProviderModels}
        onTestProvider={testProvider}
        onCopilotLogin={loginCopilot}
        onCopilotStatus={getCopilotLogin}
        onCopilotCancel={stopCopilotLogin}
      />
    {/if}
  </AppShell>
{/if}
