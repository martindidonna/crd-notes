<script lang="ts">
  export let value = 0;
  $: safeValue = Math.max(0, Math.min(100, value));
</script>

<div class="progress-track" aria-valuemin="0" aria-valuemax="100" aria-valuenow={safeValue}>
  <div class="progress-fill" style={`width: ${safeValue}%`}></div>
</div>
