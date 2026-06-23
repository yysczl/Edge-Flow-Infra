<script setup>
import { computed, inject } from "vue";

const gateway = inject("gateway");

const healthJson = computed(() => JSON.stringify(gateway.health.payload, null, 2));
</script>

<template>
  <section class="panel">
    <div class="panel-header">
      <h2>Runtime Status</h2>
      <button type="button" @click="gateway.refreshStatus">
        Refresh
      </button>
    </div>

    <div class="status-grid">
      <div>
        <span>Health</span>
        <strong>{{ gateway.health.status }}</strong>
      </div>
      <div>
        <span>Latency</span>
        <strong>{{ gateway.health.statusLatency }}</strong>
      </div>
      <div>
        <span>Unit Manager</span>
        <strong>{{ gateway.health.unitManagerAddr }}</strong>
      </div>
    </div>

    <pre class="json-view">{{ healthJson }}</pre>
  </section>
</template>
