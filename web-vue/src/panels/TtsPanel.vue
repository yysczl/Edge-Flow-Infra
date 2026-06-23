<script setup>
import { computed, inject, onBeforeUnmount, ref } from "vue";
import { synthesizeSpeech } from "../api/gateway";
import { makeObjectUrl, revokeObjectUrl } from "../utils/file";

const gateway = inject("gateway");
const input = ref("");
const voice = ref(0);
const speed = ref(1.0);
const isSubmitting = ref(false);
const audioUrl = ref("");

const canDownload = computed(() => Boolean(audioUrl.value));

async function submitTts() {
  const text = input.value.trim();
  if (!text) {
    return;
  }

  isSubmitting.value = true;
  clearAudio();

  try {
    const blob = await synthesizeSpeech(gateway.baseUrl.value, {
      model: gateway.models.tts,
      input: text,
      voice: String(voice.value || 0),
      response_format: "wav",
      speed: Number(speed.value || 1),
    });
    audioUrl.value = makeObjectUrl(blob, audioUrl.value);
  } catch (error) {
    gateway.toast(error.message);
  } finally {
    isSubmitting.value = false;
    gateway.refreshStatus();
  }
}

function clearAudio() {
  revokeObjectUrl(audioUrl.value);
  audioUrl.value = "";
}

onBeforeUnmount(clearAudio);
</script>

<template>
  <section class="panel">
    <div class="panel-header">
      <h2>Speech Synthesis</h2>
      <span class="format-pill">WAV</span>
    </div>

    <form class="stack-form" @submit.prevent="submitTts">
      <label class="field">
        <span>Input</span>
        <textarea v-model="input" rows="6" placeholder="Text to synthesize"></textarea>
      </label>
      <div class="control-grid">
        <label class="field">
          <span>Voice</span>
          <input v-model.number="voice" type="number" min="0" step="1">
        </label>
        <label class="field">
          <span>Speed</span>
          <input v-model.number="speed" type="number" min="0.1" step="0.1">
        </label>
      </div>
      <button class="primary-action" type="submit" :disabled="isSubmitting">
        {{ isSubmitting ? "Synthesizing" : "Synthesize" }}
      </button>
    </form>

    <div class="audio-result">
      <audio :src="audioUrl" controls></audio>
      <a
        :class="['download-link', { disabled: !canDownload }]"
        :href="audioUrl || '#'"
        download="speech.wav"
      >
        Download WAV
      </a>
    </div>
  </section>
</template>
