<script lang="ts">
  export let title: string;
  export let eyebrow: string;
  export let description: string;
</script>

<section class="panel panel-main">
  <p class="eyebrow">{eyebrow}</p>
  <h2>{title}</h2>
  <p class="muted">{description}</p>
</section>
