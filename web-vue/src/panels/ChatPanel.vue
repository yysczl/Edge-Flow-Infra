<script setup>
import { inject, nextTick, ref, watch } from "vue";
import { useChat } from "../composables/useChat";

const gateway = inject("gateway");
const chatInput = ref("");
const chatLog = ref(null);

const {
  messages,
  streamEnabled,
  isSending,
  sendMessage,
  clearMessages,
} = useChat(gateway.baseUrl, gateway.models, gateway.refreshStatus);

async function submitChat() {
  const value = chatInput.value;
  chatInput.value = "";
  await sendMessage(value);
  await scrollToBottom();
}

async function scrollToBottom() {
  await nextTick();
  if (chatLog.value) {
    chatLog.value.scrollTop = chatLog.value.scrollHeight;
  }
}

watch(messages, scrollToBottom, { deep: true });
</script>

<template>
  <section class="panel">
    <div class="panel-header">
      <h2>Text Generation</h2>
      <div class="panel-actions">
        <label class="toggle">
          <input v-model="streamEnabled" type="checkbox">
          <span>Stream</span>
        </label>
        <button type="button" @click="clearMessages">
          Clear
        </button>
      </div>
    </div>

    <div ref="chatLog" class="chat-log" aria-live="polite">
      <div
        v-for="(message, index) in messages"
        :key="message.id || index"
        :class="['message', message.role]"
      >
        {{ message.content }}
      </div>
    </div>

    <form class="composer" @submit.prevent="submitChat">
      <textarea
        v-model="chatInput"
        rows="3"
        placeholder="Send a message to the local model"
      ></textarea>
      <button class="primary-action" type="submit" :disabled="isSending">
        {{ isSending ? "Sending" : "Send" }}
      </button>
    </form>
  </section>
</template>
