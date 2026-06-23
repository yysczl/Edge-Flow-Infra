import { ref } from "vue";
import { completeChat, streamChat } from "../api/gateway";

let nextMessageId = 0;

export function useChat(baseUrl, models, refreshStatus) {
  const messages = ref([readyMessage()]);
  const streamEnabled = ref(true);
  const isSending = ref(false);

  async function sendMessage(text) {
    const content = String(text || "").trim();
    if (!content || isSending.value) {
      return;
    }

    const userMessage = createMessage("user", content);
    const assistantMessage = createMessage("assistant", "", { pending: true });
    const assistantId = assistantMessage.id;
    messages.value.push(userMessage, assistantMessage);
    isSending.value = true;

    const payloadMessages = apiMessages();

    try {
      if (streamEnabled.value) {
        await streamChat(baseUrl.value, models.llm, payloadMessages, (delta) => {
          updateMessage(assistantId, (message) => {
            message.content += delta;
          });
        });
      } else {
        const reply = await completeChat(baseUrl.value, models.llm, payloadMessages);
        updateMessage(assistantId, (message) => {
          message.content = reply;
        });
      }

      updateMessage(assistantId, (message) => {
        if (!message.content) {
          message.content = "(empty response)";
        }
        message.pending = false;
      });
    } catch (error) {
      messages.value = messages.value.filter((message) => message.id !== assistantId);
      messages.value.push(createMessage("error", error.message, { transient: true }));
    } finally {
      isSending.value = false;
      refreshStatus?.();
    }
  }

  function clearMessages() {
    messages.value = [readyMessage()];
  }

  function apiMessages() {
    return messages.value
      .filter((message) => {
        return ["user", "assistant"].includes(message.role)
          && !message.transient
          && !message.pending;
      })
      .map((message) => ({
        role: message.role,
        content: message.content,
      }));
  }

  function updateMessage(id, updater) {
    const message = messages.value.find((item) => item.id === id);
    if (message) {
      updater(message);
    }
  }

  return {
    messages,
    streamEnabled,
    isSending,
    sendMessage,
    clearMessages,
  };
}

function readyMessage() {
  return createMessage("assistant", "Ready.", { transient: true });
}

function createMessage(role, content, extras = {}) {
  nextMessageId += 1;
  return {
    id: `msg-${nextMessageId}`,
    role,
    content,
    ...extras,
  };
}
