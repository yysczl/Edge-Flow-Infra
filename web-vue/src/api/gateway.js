import { streamChatCompletion } from "./sse";

export const DEFAULT_MODELS = {
  llm: "rkllm-local",
  tts: "tts-local",
  asr: "asr-local",
};

export function normalizeBaseUrl(value) {
  return String(value || "").trim().replace(/\/+$/, "");
}

export function apiUrl(baseUrl, path) {
  const base = normalizeBaseUrl(baseUrl);
  return `${base}${path}`;
}

export async function getHealth(baseUrl) {
  const started = performance.now();
  const response = await fetch(apiUrl(baseUrl, "/health"), { cache: "no-store" });
  const elapsed = Math.round(performance.now() - started);
  const payload = await readJsonOrThrow(response);
  return { payload, elapsed };
}

export async function getModels(baseUrl) {
  const response = await fetch(apiUrl(baseUrl, "/v1/models"), { cache: "no-store" });
  const payload = await readJsonOrThrow(response);
  const ids = Array.isArray(payload.data)
    ? payload.data.map((item) => item.id).filter(Boolean)
    : [];

  return {
    llm: ids.find((id) => id.includes("rkllm")) || ids[0] || DEFAULT_MODELS.llm,
    tts: ids.find((id) => id.includes("tts")) || DEFAULT_MODELS.tts,
    asr: ids.find((id) => id.includes("asr")) || DEFAULT_MODELS.asr,
  };
}

export async function completeChat(baseUrl, model, messages) {
  const response = await fetch(apiUrl(baseUrl, "/v1/chat/completions"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model,
      messages,
      stream: false,
    }),
  });
  const payload = await readJsonOrThrow(response);
  return payload.choices?.[0]?.message?.content || "";
}

export async function streamChat(baseUrl, model, messages, onDelta) {
  return streamChatCompletion(apiUrl(baseUrl, "/v1/chat/completions"), {
    model,
    messages,
    stream: true,
  }, onDelta);
}

export async function transcribeAudio(baseUrl, file, model) {
  const form = new FormData();
  form.append("model", model);
  form.append("response_format", "json");
  form.append("file", file, file.name || "audio.wav");

  const response = await fetch(apiUrl(baseUrl, "/v1/audio/transcriptions"), {
    method: "POST",
    body: form,
  });
  const payload = await readJsonOrThrow(response);
  return payload.text || "";
}

export async function synthesizeSpeech(baseUrl, payload) {
  const response = await fetch(apiUrl(baseUrl, "/v1/audio/speech"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorPayload = await safeJson(response);
    throw new Error(errorPayload?.error?.message || `HTTP ${response.status}`);
  }

  return response.blob();
}

export async function runVoiceConversation(baseUrl, params) {
  const form = new FormData();
  form.append("file", params.file, params.file.name || "audio.wav");
  form.append("model", params.model);
  form.append("voice", String(params.voice || "0"));
  form.append("speed", String(params.speed || "1.0"));
  form.append("response_format", "json");
  form.append("system_prompt", params.systemPrompt || "");

  const response = await fetch(apiUrl(baseUrl, "/v1/audio/conversations"), {
    method: "POST",
    body: form,
  });
  return readJsonOrThrow(response);
}

export async function readJsonOrThrow(response) {
  const payload = await safeJson(response);
  if (!response.ok) {
    throw new Error(payload?.error?.message || `HTTP ${response.status}`);
  }
  return payload;
}

export async function safeJson(response) {
  try {
    return await response.json();
  } catch (_) {
    return null;
  }
}
