<script setup>
import { computed, inject, onBeforeUnmount, ref } from "vue";
import { runVoiceConversation } from "../api/gateway";
import { base64ToBlob } from "../utils/base64";
import { makeObjectUrl, revokeObjectUrl, setFileInput } from "../utils/file";

const gateway = inject("gateway");
const fileInput = ref(null);
const selectedFile = ref(null);
const systemPrompt = ref("You are a local AI assistant running on an edge device. Keep answers concise.");
const speaker = ref(0);
const speed = ref(1.0);
const transcript = ref("");
const reply = ref("");
const audioUrl = ref("");
const isSubmitting = ref(false);

const isRecordingThis = computed(() => gateway.recorder.activeTarget.value === "voice");
const isRecordingOther = computed(() => {
  return Boolean(gateway.recorder.activeTarget.value && gateway.recorder.activeTarget.value !== "voice");
});

function handleFileChange(event) {
  selectedFile.value = event.target.files?.[0] || null;
}

async function submitVoiceConversation() {
  const file = selectedFile.value || gateway.recorder.recordedFiles.voice;
  if (!file) {
    gateway.toast("Select or record a WAV file");
    return;
  }

  isSubmitting.value = true;
  transcript.value = "";
  reply.value = "";
  clearAudio();

  try {
    const payload = await runVoiceConversation(gateway.baseUrl.value, {
      file,
      model: gateway.models.llm,
      voice: speaker.value,
      speed: speed.value,
      systemPrompt: systemPrompt.value,
    });

    transcript.value = payload.transcript || "";
    reply.value = payload.reply || "";

    if (payload.audio?.data) {
      const blob = base64ToBlob(payload.audio.data, "audio/wav");
      audioUrl.value = makeObjectUrl(blob, audioUrl.value);
    }
  } catch (error) {
    gateway.toast(error.message);
  } finally {
    isSubmitting.value = false;
    gateway.refreshStatus();
  }
}

async function toggleRecording() {
  try {
    const file = await gateway.recorder.toggleRecording("voice");
    if (file) {
      selectedFile.value = file;
      setFileInput(fileInput.value, file);
      gateway.toast("Recording captured");
    }
  } catch (error) {
    gateway.toast(error.message);
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
      <h2>Voice Conversation</h2>
      <span class="format-pill">ASR -> LLM -> TTS</span>
    </div>

    <form class="stack-form" @submit.prevent="submitVoiceConversation">
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
      <label class="field">
        <span>System Prompt</span>
        <textarea v-model="systemPrompt" rows="3"></textarea>
      </label>
      <div class="control-grid">
        <label class="field">
          <span>Voice</span>
          <input v-model.number="speaker" type="number" min="0" step="1">
        </label>
        <label class="field">
          <span>Speed</span>
          <input v-model.number="speed" type="number" min="0.1" step="0.1">
        </label>
      </div>
      <div class="action-row">
        <button class="primary-action" type="submit" :disabled="isSubmitting">
          {{ isSubmitting ? "Running" : "Run Conversation" }}
        </button>
      </div>
    </form>

    <div class="voice-result">
      <div>
        <label for="voiceTranscript">Transcript</label>
        <textarea id="voiceTranscript" v-model="transcript" rows="4" readonly></textarea>
      </div>
      <div>
        <label for="voiceReply">Reply</label>
        <textarea id="voiceReply" v-model="reply" rows="4" readonly></textarea>
      </div>
      <audio :src="audioUrl" controls></audio>
    </div>
  </section>
</template>
