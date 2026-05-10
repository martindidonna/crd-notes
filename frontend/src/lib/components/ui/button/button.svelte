<script lang="ts">
  import { cn } from "$lib/utils/cn";

  export let type: "button" | "submit" | "reset" = "button";
  export let variant: "primary" | "secondary" | "ghost" = "primary";
  export let size: "sm" | "md" | "icon" = "md";
  export let disabled = false;
  export let className = "";
</script>

<button
  {type}
  {disabled}
  class={cn("ui-button", `ui-button-${variant}`, `ui-button-${size}`, className)}
  on:click
>
  <slot />
</button>
