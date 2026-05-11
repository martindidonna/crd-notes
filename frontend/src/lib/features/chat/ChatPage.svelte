<script lang="ts">
  import { Plus, Send, Trash2 } from "lucide-svelte";
  import { Button } from "$lib/components/ui/button";
  import type { ChatMessage, ChatThread } from "$lib/api/types";
  import { renderMarkdown } from "$lib/utils/markdown";

  export let threads: ChatThread[] = [];
  export let activeThreadId = "";
  export let messages: ChatMessage[] = [];
  export let loading = false;
  export let onNewThread: () => Promise<void>;
  export let onSelectThread: (threadId: string) => Promise<void>;
  export let onDeleteThread: (threadId: string) => Promise<void>;
  export let onSend: (content: string) => Promise<void>;
  let content = "";

</script>

<section class="chat-shell">
  <aside class="chat-thread-rail">
    <div class="chat-thread-head">
      <div><p class="eyebrow">Cronologia</p><h2>Conversazioni</h2></div>
      <Button size="sm" variant="secondary" on:click={onNewThread}><Plus size={15} />Nuova</Button>
    </div>
    <div class="chat-thread-list">
      {#each threads as thread}
        <div class:active={thread.id === activeThreadId} class="chat-thread-item">
          <button class="chat-thread" type="button" on:click={() => onSelectThread(thread.id)}>
            <strong>{thread.title}</strong>
            <span>{new Date(thread.updated_at).toLocaleString("it-IT")}</span>
          </button>
          <Button size="icon" variant="ghost" on:click={() => onDeleteThread(thread.id)} aria-label="Elimina chat"><Trash2 size={15} /></Button>
        </div>
      {/each}
    </div>
  </aside>
  <section class="chat-stage">
    <div class="chat-messages">
      {#if !messages.length}
        <div class="chat-welcome"><h3>Nuova chat</h3><p>Chiedi a Cardinal usando il contesto del workspace e della knowledge.</p></div>
      {/if}
      {#each messages as message}
        <article class:assistant={message.role !== "user"} class:user={message.role === "user"} class="chat-message">
          <div class="chat-message-meta"><strong>{message.role === "user" ? "Tu" : "Cardinal"}</strong><span>{message.model}</span></div>
          <div class="chat-message-body markdown-body">{@html renderMarkdown(message.content)}</div>
          {#if message.sources?.length}
            <details class="chat-sources"><summary>Fonti ({message.sources.length})</summary>
              {#each message.sources as source}
                <p>{source.entry_title}: {source.snippet}</p>
              {/each}
            </details>
          {/if}
        </article>
      {/each}
    </div>
    <form class="chat-composer" on:submit|preventDefault={async () => { const value = content.trim(); if (!value) return; content = ""; await onSend(value); }}>
      <div class="chat-composer-row">
        <textarea bind:value={content} rows="2" placeholder="Chiedi a Cardinal."></textarea>
        <Button type="submit" disabled={loading || !content.trim()}><Send size={15} />Invia</Button>
      </div>
    </form>
  </section>
</section>
