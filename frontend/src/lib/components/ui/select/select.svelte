<script lang="ts">
  import { cn } from "$lib/utils/cn";

  export let value = "";
  export let label = "";
  export let className = "";
  export let options: Array<{ value: string; label: string }> = [];
</script>

<label class={cn("field", className)}>
  {#if label}
    <span>{label}</span>
  {/if}
  <select bind:value on:change>
    {#each options as option}
      <option value={option.value}>{option.label}</option>
    {/each}
  </select>
</label>
