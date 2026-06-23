<script setup>
defineProps({
  health: {
    type: Object,
    required: true,
  },
});
</script>

<template>
  <header class="topbar">
    <div>
      <p class="eyebrow">OpenAI-compatible edge inference</p>
      <h1>Edge AI Gateway Console</h1>
    </div>
    <div class="health-strip" aria-live="polite">
      <span :class="['status-dot', health.kind]"></span>
      <span>{{ health.text }}</span>
      <span>Latency: {{ health.latency }}</span>
    </div>
  </header>
</template>
