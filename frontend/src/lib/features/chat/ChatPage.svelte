<script lang="ts">
  import { Plus, Send, Trash2 } from "lucide-svelte";
  import { Button } from "$lib/components/ui/button";
  import type { ChatMessage, ChatThread } from "$lib/api/types";

  export let threads: ChatThread[] = [];
  export let activeThreadId = "";
  export let messages: ChatMessage[] = [];
  export let loading = false;
  export let onNewThread: () => Promise<void>;
  export let onSelectThread: (threadId: string) => Promise<void>;
  export let onDeleteThread: (threadId: string) => Promise<void>;
  export let onSend: (content: string) => Promise<void>;
  let content = "";

  function escapeHtml(value: string) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function renderInline(value: string) {
    return escapeHtml(value)
      .replace(/&lt;br\s*\/?&gt;/gi, "<br>")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      .replace(/`(.+?)`/g, "<code class=\"chat-inline-code\">$1</code>");
  }

  function isTableSeparator(line: string) {
    return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);
  }

  function isTableRow(line: string) {
    return line.trim().startsWith("|") && line.trim().endsWith("|");
  }

  function tableCells(line: string) {
    return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim());
  }

  function renderMarkdown(value: string) {
    const lines = String(value || "").replace(/\r\n/g, "\n").split("\n");
    const blocks: string[] = [];
    let paragraph: string[] = [];
    let tableRows: string[][] = [];
    let tableHasHeader = false;

    const flushParagraph = () => {
      if (!paragraph.length) return;
      blocks.push(`<p>${renderInline(paragraph.join(" "))}</p>`);
      paragraph = [];
    };

    const flushTable = () => {
      if (!tableRows.length) return;
      const [head, ...body] = tableRows;
      const header = tableHasHeader ? head : [];
      const rows = tableHasHeader ? body : tableRows;
      const thead = header.length
        ? `<thead><tr>${header.map((cell) => `<th>${renderInline(cell)}</th>`).join("")}</tr></thead>`
        : "";
      const tbody = `<tbody>${rows
        .map((row) => `<tr>${row.map((cell) => `<td>${renderInline(cell)}</td>`).join("")}</tr>`)
        .join("")}</tbody>`;
      blocks.push(`<div class="chat-table-wrap"><table class="chat-table">${thead}${tbody}</table></div>`);
      tableRows = [];
      tableHasHeader = false;
    };

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) {
        flushTable();
        flushParagraph();
        continue;
      }
      if (isTableSeparator(trimmed) && tableRows.length) {
        tableHasHeader = true;
        continue;
      }
      if (isTableRow(trimmed)) {
        flushParagraph();
        tableRows.push(tableCells(trimmed));
        continue;
      }
      flushTable();
      const heading = trimmed.match(/^(#{1,3})\s+(.+)$/);
      if (heading) {
        flushParagraph();
        const tag = heading[1].length === 1 ? "h3" : heading[1].length === 2 ? "h4" : "h5";
        blocks.push(`<${tag} class="chat-heading">${renderInline(heading[2])}</${tag}>`);
        continue;
      }
      if (/^[-*]\s+/.test(trimmed)) {
        flushParagraph();
        blocks.push(`<ul><li>${renderInline(trimmed.replace(/^[-*]\s+/, ""))}</li></ul>`);
        continue;
      }
      paragraph.push(trimmed);
    }

    flushTable();
    flushParagraph();
    return blocks.join("");
  }
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
          <div class="chat-message-body">{@html renderMarkdown(message.content)}</div>
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
