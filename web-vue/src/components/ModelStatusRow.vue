<script setup>
defineProps({
  models: {
    type: Object,
    required: true,
  },
  busy: {
    type: Object,
    required: true,
  },
});
</script>

<template>
  <section class="model-row" aria-label="Models">
    <div :class="['model-tile', { busy: busy.llm }]">
      <span>LLM</span>
      <strong>{{ models.llm }}</strong>
      <small>{{ busy.llm ? "Busy" : "Idle" }}</small>
    </div>
    <div :class="['model-tile', { busy: busy.asr }]">
      <span>ASR</span>
      <strong>{{ models.asr }}</strong>
      <small>{{ busy.asr ? "Busy" : "Idle" }}</small>
    </div>
    <div :class="['model-tile', { busy: busy.tts }]">
      <span>TTS</span>
      <strong>{{ models.tts }}</strong>
      <small>{{ busy.tts ? "Busy" : "Idle" }}</small>
    </div>
  </section>
</template>
