<script setup>
import { onMounted, provide, ref } from "vue";
import ConnectionBar from "./components/ConnectionBar.vue";
import ModelStatusRow from "./components/ModelStatusRow.vue";
import TabsNav from "./components/TabsNav.vue";
import Toast from "./components/Toast.vue";
import TopBar from "./components/TopBar.vue";
import { normalizeBaseUrl } from "./api/gateway";
import { useAudioRecorder } from "./composables/useAudioRecorder";
import { useGatewayStatus } from "./composables/useGatewayStatus";
import { useToast } from "./composables/useToast";
import AsrPanel from "./panels/AsrPanel.vue";
import ChatPanel from "./panels/ChatPanel.vue";
import DocsPanel from "./panels/DocsPanel.vue";
import StatusPanel from "./panels/StatusPanel.vue";
import TtsPanel from "./panels/TtsPanel.vue";
import VoicePanel from "./panels/VoicePanel.vue";

const BASE_URL_KEY = "edgeGatewayBaseUrl";

const tabs = [
  { id: "chat", label: "Text" },
  { id: "asr", label: "Speech to Text" },
  { id: "tts", label: "Text to Speech" },
  { id: "voice", label: "Voice Chat" },
  { id: "status", label: "Status" },
  { id: "docs", label: "API Docs" },
];

const activeTab = ref("chat");
const baseUrl = ref(normalizeBaseUrl(localStorage.getItem(BASE_URL_KEY) || import.meta.env.VITE_GATEWAY_BASE_URL || ""));
const toastState = useToast();
const toastMessage = toastState.message;
const toastVisible = toastState.visible;
const recorder = useAudioRecorder();
const gatewayStatus = useGatewayStatus(baseUrl);

function saveBaseUrl() {
  baseUrl.value = normalizeBaseUrl(baseUrl.value);
  if (baseUrl.value) {
    localStorage.setItem(BASE_URL_KEY, baseUrl.value);
  } else {
    localStorage.removeItem(BASE_URL_KEY);
  }
  toastState.toast("Base URL saved");
  gatewayStatus.refreshStatus();
}

provide("gateway", {
  baseUrl,
  models: gatewayStatus.models,
  busy: gatewayStatus.busy,
  health: gatewayStatus.health,
  refreshStatus: gatewayStatus.refreshStatus,
  refreshModels: gatewayStatus.refreshModels,
  toast: toastState.toast,
  recorder,
});

onMounted(() => {
  gatewayStatus.refreshStatus();
});
</script>

<template>
  <div class="app-shell">
    <TopBar :health="gatewayStatus.health" />
    <ConnectionBar
      v-model="baseUrl"
      @save="saveBaseUrl"
      @refresh="gatewayStatus.refreshStatus"
    />
    <ModelStatusRow :models="gatewayStatus.models" :busy="gatewayStatus.busy" />
    <TabsNav :tabs="tabs" :active-tab="activeTab" @select="activeTab = $event" />

    <main>
      <ChatPanel v-show="activeTab === 'chat'" />
      <AsrPanel v-show="activeTab === 'asr'" />
      <TtsPanel v-show="activeTab === 'tts'" />
      <VoicePanel v-show="activeTab === 'voice'" />
      <StatusPanel v-show="activeTab === 'status'" />
      <DocsPanel v-show="activeTab === 'docs'" />
    </main>

    <Toast :message="toastMessage" :visible="toastVisible" />
  </div>
</template>
