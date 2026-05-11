<script lang="ts">
  import type { ProviderSettings } from "$lib/api/types";

  export let settings: Record<string, unknown> | null = null;
  export let providerModels: Record<string, string[]> = {};
  export let selectedProvider = "";
  export let selectedModel = "";
  export let disabled = false;

  const providerLabels: Record<string, string> = {
    openai: "OpenAI",
    openrouter: "OpenRouter",
    ollama: "Ollama",
    lmstudio: "LM Studio",
    copilot: "GitHub Copilot"
  };

  function providersFromSettings() {
    const providers = (settings?.providers ?? {}) as Record<string, ProviderSettings>;
    return Object.entries(providers).filter(([, item]) => item?.enabled);
  }

  function unique(values: Array<string | undefined | null>) {
    return Array.from(new Set(values.filter((value): value is string => Boolean(value))));
  }

  $: enabledProviders = providersFromSettings();
  $: providerSettings = ((settings?.providers ?? {}) as Record<string, ProviderSettings>)[selectedProvider];
  $: modelOptions = unique([...(providerModels[selectedProvider] ?? []), ...(providerSettings?.available_models ?? []), providerSettings?.model]);
  $: if (!selectedProvider && settings?.active_provider) selectedProvider = settings.active_provider as string;
  $: if (enabledProviders.length && !enabledProviders.some(([name]) => name === selectedProvider)) selectedProvider = enabledProviders[0][0];
  $: if ((!selectedModel || !modelOptions.includes(selectedModel)) && providerSettings?.model) selectedModel = providerSettings.model;
  $: if (!selectedModel && modelOptions.length) selectedModel = modelOptions[0];
</script>

<div class="summary-selects ai-model-picker">
  <label>
    <span>Provider AI</span>
    <select bind:value={selectedProvider} {disabled}>
      {#if enabledProviders.length}
        {#each enabledProviders as [name]}
          <option value={name}>{providerLabels[name] ?? name}</option>
        {/each}
      {:else}
        <option value="">Nessun provider abilitato</option>
      {/if}
    </select>
  </label>
  <label>
    <span>Modello</span>
    <select bind:value={selectedModel} disabled={disabled || !selectedProvider}>
      {#if modelOptions.length}
        {#each modelOptions as model}
          <option value={model}>{model}</option>
        {/each}
      {:else}
        <option value="">Modello non configurato</option>
      {/if}
    </select>
  </label>
</div>
