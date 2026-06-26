<script setup>
import { computed, inject, ref } from "vue";
import { transcribeAudio } from "../api/gateway";
import { setFileInput } from "../utils/file";

const gateway = inject("gateway");
const fileInput = ref(null);
const selectedFile = ref(null);
const output = ref("");
const isSubmitting = ref(false);

const isRecordingThis = computed(() => gateway.recorder.activeTarget.value === "asr");
const isRecordingOther = computed(() => {
  return Boolean(gateway.recorder.activeTarget.value && gateway.recorder.activeTarget.value !== "asr");
});

function handleFileChange(event) {
  selectedFile.value = event.target.files?.[0] || null;
}

async function submitAsr() {
  const file = selectedFile.value || gateway.recorder.recordedFiles.asr;
  if (!file) {
    gateway.toast("Select or record a WAV file");
    return;
  }

  isSubmitting.value = true;
  output.value = "";

  try {
    output.value = await transcribeAudio(gateway.baseUrl.value, file, gateway.models.asr);
  } catch (error) {
    output.value = error.message;
  } finally {
    isSubmitting.value = false;
    gateway.refreshStatus();
  }
}

async function toggleRecording() {
  try {
    const file = await gateway.recorder.toggleRecording("asr");
    if (file) {
      selectedFile.value = file;
      setFileInput(fileInput.value, file);
      gateway.toast("Recording captured");
    }
  } catch (error) {
    gateway.toast(error.message);
  }
}
</script>

<template>
  <section class="panel">
    <div class="panel-header">
      <h2>Speech Recognition</h2>
      <span class="format-pill">WAV</span>
    </div>

    <form class="stack-form" @submit.prevent="submitAsr">
      <div class="record-file-row">
        <button
          class="record-action"
          type="button"
          :class="{ recording: isRecordingThis }"
          :disabled="isRecordingOther"
          @click="toggleRecording"
        >
          {{ isRecordingThis ? "Stop" : "Record" }}
        </button>
        <label class="file-drop">
          <span>WAV file</span>
          <input
            ref="fileInput"
            type="file"
            accept=".wav,audio/wav,audio/x-wav"
            @change="handleFileChange"
          >
        </label>
      </div>
      <div class="action-row">
        <button class="primary-action" type="submit" :disabled="isSubmitting">
          {{ isSubmitting ? "Transcribing" : "Transcribe" }}
        </button>
      </div>
    </form>

    <div class="output-block">
      <label for="asrOutput">Transcript</label>
      <textarea id="asrOutput" v-model="output" rows="8" readonly></textarea>
    </div>
  </section>
</template>
