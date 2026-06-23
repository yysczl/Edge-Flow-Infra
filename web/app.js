const state = {
  baseUrl: localStorage.getItem("edgeGatewayBaseUrl") || "http://127.0.0.1:8000",
  models: {
    llm: "rkllm-local",
    tts: "tts-local",
    asr: "asr-local",
  },
  messages: [],
  recording: null,
  recordedFiles: {
    asr: null,
    voice: null,
  },
};

const els = {};

document.addEventListener("DOMContentLoaded", () => {
  bindElements();
  bindTabs();
  bindForms();
  els.baseUrlInput.value = state.baseUrl;
  renderExamples();
  appendMessage("assistant", "Ready.");
  refreshStatus();
});

function bindElements() {
  [
    "baseUrlInput",
    "saveBaseUrlBtn",
    "refreshStatusBtn",
    "statusRefreshBtn",
    "healthDot",
    "healthText",
    "latencyText",
    "llmModel",
    "asrModel",
    "ttsModel",
    "llmBusy",
    "asrBusy",
    "ttsBusy",
    "chatLog",
    "chatForm",
    "chatInput",
    "sendChatBtn",
    "streamToggle",
    "asrForm",
    "asrFile",
    "asrOutput",
    "transcribeBtn",
    "recordAsrBtn",
    "ttsForm",
    "ttsInput",
    "ttsVoice",
    "ttsSpeed",
    "synthesizeBtn",
    "ttsAudio",
    "ttsDownload",
    "voiceForm",
    "voiceFile",
    "voiceSystemPrompt",
    "voiceSpeaker",
    "voiceSpeed",
    "voiceSubmitBtn",
    "recordVoiceBtn",
    "voiceTranscript",
    "voiceReply",
    "voiceAudio",
    "statusHealth",
    "statusLatency",
    "unitManagerAddr",
    "healthJson",
    "curlHealth",
    "curlModels",
    "curlChat",
    "curlSpeech",
    "curlTranscribe",
    "curlConversation",
    "copyModelsCurl",
    "toast",
  ].forEach((id) => {
    els[id] = document.getElementById(id);
  });
}

function bindTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(".panel").forEach((item) => item.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById(tab.dataset.tab).classList.add("active");
    });
  });
}

function bindForms() {
  els.saveBaseUrlBtn.addEventListener("click", () => {
    state.baseUrl = normalizeBaseUrl(els.baseUrlInput.value);
    els.baseUrlInput.value = state.baseUrl;
    localStorage.setItem("edgeGatewayBaseUrl", state.baseUrl);
    renderExamples();
    refreshStatus();
    toast("Base URL saved");
  });

  els.refreshStatusBtn.addEventListener("click", refreshStatus);
  els.statusRefreshBtn.addEventListener("click", refreshStatus);
  els.chatForm.addEventListener("submit", submitChat);
  els.asrForm.addEventListener("submit", submitAsr);
  els.ttsForm.addEventListener("submit", submitTts);
  els.voiceForm.addEventListener("submit", submitVoiceConversation);
  els.recordAsrBtn.addEventListener("click", () => toggleRecording("asr"));
  els.recordVoiceBtn.addEventListener("click", () => toggleRecording("voice"));
  els.copyModelsCurl.addEventListener("click", () => copyText(els.curlModels.textContent));
}

function normalizeBaseUrl(value) {
  const trimmed = String(value || "").trim();
  return trimmed.replace(/\/+$/, "") || "http://127.0.0.1:8000";
}

function apiUrl(path) {
  return `${state.baseUrl}${path}`;
}

async function refreshStatus() {
  const started = performance.now();
  setHealth("unknown", "Checking", "--");

  try {
    const response = await fetch(apiUrl("/health"), { cache: "no-store" });
    const elapsed = Math.round(performance.now() - started);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    setHealth("ok", data.status || "ok", `${elapsed} ms`);
    renderHealth(data, elapsed);
    await refreshModels();
  } catch (error) {
    setHealth("bad", "Offline", "--");
    els.statusHealth.textContent = "Offline";
    els.statusLatency.textContent = "--";
    els.healthJson.textContent = JSON.stringify({ error: error.message }, null, 2);
  }
}

async function refreshModels() {
  try {
    const response = await fetch(apiUrl("/v1/models"), { cache: "no-store" });
    if (!response.ok) {
      return;
    }
    const payload = await response.json();
    const ids = Array.isArray(payload.data)
      ? payload.data.map((item) => item.id).filter(Boolean)
      : [];

    state.models.llm = ids.find((id) => id.includes("rkllm")) || ids[0] || state.models.llm;
    state.models.tts = ids.find((id) => id.includes("tts")) || state.models.tts;
    state.models.asr = ids.find((id) => id.includes("asr")) || state.models.asr;
    renderModels();
    renderExamples();
  } catch (_) {
    renderModels();
  }
}

function setHealth(kind, text, latency) {
  els.healthDot.className = `status-dot ${kind}`;
  els.healthText.textContent = text;
  els.latencyText.textContent = `Latency: ${latency}`;
}

function renderHealth(data, elapsed) {
  state.models.llm = data.rkllm?.model || state.models.llm;
  state.models.tts = data.tts?.model || state.models.tts;
  state.models.asr = data.asr?.model || state.models.asr;

  els.llmBusy.textContent = data.rkllm?.busy ? "Busy" : "Idle";
  els.ttsBusy.textContent = data.tts?.busy ? "Busy" : "Idle";
  els.asrBusy.textContent = data.asr?.busy ? "Busy" : "Idle";

  els.llmBusy.closest(".model-tile").classList.toggle("busy", Boolean(data.rkllm?.busy));
  els.ttsBusy.closest(".model-tile").classList.toggle("busy", Boolean(data.tts?.busy));
  els.asrBusy.closest(".model-tile").classList.toggle("busy", Boolean(data.asr?.busy));

  renderModels();

  els.statusHealth.textContent = data.status || "ok";
  els.statusLatency.textContent = `${elapsed} ms`;
  els.unitManagerAddr.textContent = `${data.unit_manager?.host || "--"}:${data.unit_manager?.port || "--"}`;
  els.healthJson.textContent = JSON.stringify(data, null, 2);
}

function renderModels() {
  els.llmModel.textContent = state.models.llm;
  els.ttsModel.textContent = state.models.tts;
  els.asrModel.textContent = state.models.asr;
}

async function submitChat(event) {
  event.preventDefault();
  const text = els.chatInput.value.trim();
  if (!text) {
    return;
  }

  state.messages.push({ role: "user", content: text });
  appendMessage("user", text);
  els.chatInput.value = "";
  els.sendChatBtn.disabled = true;

  const assistantNode = appendMessage("assistant", "");
  try {
    if (els.streamToggle.checked) {
      await streamChat(assistantNode);
    } else {
      await completeChat(assistantNode);
    }
    state.messages.push({ role: "assistant", content: assistantNode.textContent });
  } catch (error) {
    assistantNode.remove();
    appendMessage("error", error.message);
  } finally {
    els.sendChatBtn.disabled = false;
    refreshStatus();
  }
}

async function completeChat(node) {
  const response = await fetch(apiUrl("/v1/chat/completions"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: state.models.llm,
      messages: state.messages,
      stream: false,
    }),
  });

  const payload = await readJsonOrThrow(response);
  const content = payload.choices?.[0]?.message?.content || "";
  node.textContent = content || "(empty response)";
}

async function streamChat(node) {
  const response = await fetch(apiUrl("/v1/chat/completions"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: state.models.llm,
      messages: state.messages,
      stream: true,
    }),
  });

  if (!response.ok || !response.body) {
    const payload = await safeJson(response);
    throw new Error(payload?.error?.message || `HTTP ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() || "";
    for (const event of events) {
      const line = event.split("\n").find((item) => item.startsWith("data:"));
      if (!line) {
        continue;
      }
      const data = line.slice(5).trim();
      if (!data || data === "[DONE]") {
        continue;
      }
      try {
        const payload = JSON.parse(data);
        if (payload.error?.message) {
          throw new Error(payload.error.message);
        }
        const delta = payload.choices?.[0]?.delta?.content || "";
        if (delta) {
          node.textContent += delta;
          els.chatLog.scrollTop = els.chatLog.scrollHeight;
        }
      } catch (_) {
        node.textContent += data;
      }
    }
  }

  if (!node.textContent) {
    node.textContent = "(empty response)";
  }
}

function appendMessage(role, text) {
  const node = document.createElement("div");
  node.className = `message ${role}`;
  node.textContent = text;
  els.chatLog.appendChild(node);
  els.chatLog.scrollTop = els.chatLog.scrollHeight;
  return node;
}

async function submitAsr(event) {
  event.preventDefault();
  const file = els.asrFile.files[0] || state.recordedFiles.asr;
  if (!file) {
    toast("Select or record a WAV file");
    return;
  }

  els.transcribeBtn.disabled = true;
  els.asrOutput.value = "";
  try {
    const text = await transcribeFile(file);
    els.asrOutput.value = text;
  } catch (error) {
    els.asrOutput.value = error.message;
  } finally {
    els.transcribeBtn.disabled = false;
    refreshStatus();
  }
}

async function transcribeFile(file) {
  const form = new FormData();
  form.append("model", state.models.asr);
  form.append("response_format", "json");
  form.append("file", file, file.name || "audio.wav");

  const response = await fetch(apiUrl("/v1/audio/transcriptions"), {
    method: "POST",
    body: form,
  });
  const payload = await readJsonOrThrow(response);
  return payload.text || "";
}

async function submitTts(event) {
  event.preventDefault();
  const input = els.ttsInput.value.trim();
  if (!input) {
    return;
  }

  els.synthesizeBtn.disabled = true;
  clearAudio(els.ttsAudio, els.ttsDownload);
  try {
    const blob = await synthesizeSpeech(input, els.ttsVoice.value, els.ttsSpeed.value);
    setAudioResult(els.ttsAudio, els.ttsDownload, blob, "speech.wav");
  } catch (error) {
    toast(error.message);
  } finally {
    els.synthesizeBtn.disabled = false;
    refreshStatus();
  }
}

async function synthesizeSpeech(input, voice, speed) {
  const response = await fetch(apiUrl("/v1/audio/speech"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: state.models.tts,
      input,
      voice: String(voice || "0"),
      response_format: "wav",
      speed: Number(speed || 1),
    }),
  });

  if (!response.ok) {
    const payload = await safeJson(response);
    throw new Error(payload?.error?.message || `HTTP ${response.status}`);
  }

  return response.blob();
}

async function submitVoiceConversation(event) {
  event.preventDefault();
  const file = els.voiceFile.files[0] || state.recordedFiles.voice;
  if (!file) {
    toast("Select or record a WAV file");
    return;
  }

  els.voiceSubmitBtn.disabled = true;
  els.voiceTranscript.value = "";
  els.voiceReply.value = "";
  clearAudio(els.voiceAudio);
  try {
    const form = new FormData();
    form.append("file", file, file.name || "audio.wav");
    form.append("model", state.models.llm);
    form.append("voice", String(els.voiceSpeaker.value || "0"));
    form.append("speed", String(els.voiceSpeed.value || "1.0"));
    form.append("response_format", "json");
    form.append("system_prompt", els.voiceSystemPrompt.value || "");

    const response = await fetch(apiUrl("/v1/audio/conversations"), {
      method: "POST",
      body: form,
    });
    const payload = await readJsonOrThrow(response);
    els.voiceTranscript.value = payload.transcript || "";
    els.voiceReply.value = payload.reply || "";

    if (payload.audio?.data) {
      const blob = base64ToBlob(payload.audio.data, "audio/wav");
      els.voiceAudio.src = URL.createObjectURL(blob);
    }
  } catch (error) {
    toast(error.message);
  } finally {
    els.voiceSubmitBtn.disabled = false;
    refreshStatus();
  }
}

async function toggleRecording(target) {
  if (state.recording) {
    const recording = state.recording;
    await stopRecording(recording);
    state.recording = null;
    updateRecordButtons();
    return;
  }

  try {
    state.recording = await startRecording(target);
    updateRecordButtons(target);
  } catch (error) {
    toast(error.message);
  }
}

async function startRecording(target) {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error("Microphone recording is not available in this browser");
  }

  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  const audioContext = new AudioContextClass();
  const source = audioContext.createMediaStreamSource(stream);
  const processor = audioContext.createScriptProcessor(4096, 1, 1);
  const monitor = audioContext.createGain();
  monitor.gain.value = 0;
  const chunks = [];

  processor.onaudioprocess = (event) => {
    chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
  };

  source.connect(processor);
  processor.connect(monitor);
  monitor.connect(audioContext.destination);

  return { target, stream, audioContext, source, processor, monitor, chunks, sampleRate: audioContext.sampleRate };
}

async function stopRecording(recording) {
  recording.processor.disconnect();
  recording.monitor.disconnect();
  recording.source.disconnect();
  recording.stream.getTracks().forEach((track) => track.stop());
  await recording.audioContext.close();

  const merged = mergeFloat32(recording.chunks);
  const wav = encodeWav(resampleFloat32(merged, recording.sampleRate, 16000), 16000);
  const file = new File([wav], "recording.wav", { type: "audio/wav" });
  state.recordedFiles[recording.target] = file;
  setFileInput(recording.target === "asr" ? els.asrFile : els.voiceFile, file);
  toast("Recording captured");
}

function updateRecordButtons(activeTarget) {
  els.recordAsrBtn.textContent = activeTarget === "asr" ? "Stop" : "Record";
  els.recordVoiceBtn.textContent = activeTarget === "voice" ? "Stop" : "Record";
  els.recordAsrBtn.disabled = Boolean(activeTarget && activeTarget !== "asr");
  els.recordVoiceBtn.disabled = Boolean(activeTarget && activeTarget !== "voice");
}

function mergeFloat32(chunks) {
  const length = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const merged = new Float32Array(length);
  let offset = 0;
  chunks.forEach((chunk) => {
    merged.set(chunk, offset);
    offset += chunk.length;
  });
  return merged;
}

function resampleFloat32(input, sourceRate, targetRate) {
  if (sourceRate === targetRate) {
    return input;
  }

  const ratio = sourceRate / targetRate;
  const outputLength = Math.round(input.length / ratio);
  const output = new Float32Array(outputLength);
  for (let index = 0; index < outputLength; index += 1) {
    const sourceIndex = index * ratio;
    const before = Math.floor(sourceIndex);
    const after = Math.min(before + 1, input.length - 1);
    const weight = sourceIndex - before;
    output[index] = input[before] * (1 - weight) + input[after] * weight;
  }
  return output;
}

function encodeWav(samples, sampleRate) {
  const bytesPerSample = 2;
  const blockAlign = bytesPerSample;
  const buffer = new ArrayBuffer(44 + samples.length * bytesPerSample);
  const view = new DataView(buffer);

  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + samples.length * bytesPerSample, true);
  writeString(view, 8, "WAVE");
  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * blockAlign, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, 16, true);
  writeString(view, 36, "data");
  view.setUint32(40, samples.length * bytesPerSample, true);

  let offset = 44;
  for (let index = 0; index < samples.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, samples[index]));
    view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
    offset += 2;
  }

  return buffer;
}

function writeString(view, offset, value) {
  for (let index = 0; index < value.length; index += 1) {
    view.setUint8(offset + index, value.charCodeAt(index));
  }
}

function setFileInput(input, file) {
  if (typeof DataTransfer === "undefined") {
    return;
  }
  const dataTransfer = new DataTransfer();
  dataTransfer.items.add(file);
  input.files = dataTransfer.files;
}

function setAudioResult(audio, link, blob, filename) {
  const url = URL.createObjectURL(blob);
  audio.src = url;
  if (link) {
    link.href = url;
    link.download = filename;
    link.classList.remove("disabled");
  }
}

function clearAudio(audio, link) {
  audio.removeAttribute("src");
  audio.load();
  if (link) {
    link.href = "#";
    link.classList.add("disabled");
  }
}

function base64ToBlob(value, type) {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return new Blob([bytes], { type });
}

async function readJsonOrThrow(response) {
  const payload = await safeJson(response);
  if (!response.ok) {
    throw new Error(payload?.error?.message || `HTTP ${response.status}`);
  }
  return payload;
}

async function safeJson(response) {
  try {
    return await response.json();
  } catch (_) {
    return null;
  }
}

function renderExamples() {
  const base = state.baseUrl;
  els.curlHealth.textContent = `curl ${base}/health`;
  els.curlModels.textContent = `curl ${base}/v1/models`;
  els.curlChat.textContent = `curl ${base}/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -d '{"model":"${state.models.llm}","messages":[{"role":"user","content":"hello"}],"stream":false}'`;
  els.curlSpeech.textContent = `curl ${base}/v1/audio/speech \\
  -H "Content-Type: application/json" \\
  -d '{"model":"${state.models.tts}","input":"hello","voice":"0","response_format":"wav","speed":1.0}' \\
  --output speech.wav`;
  els.curlTranscribe.textContent = `curl ${base}/v1/audio/transcriptions \\
  -F model=${state.models.asr} \\
  -F response_format=json \\
  -F file=@sample.wav`;
  els.curlConversation.textContent = `curl ${base}/v1/audio/conversations \\
  -F file=@sample.wav \\
  -F model=${state.models.llm} \\
  -F voice=0 \\
  -F speed=1.0`;
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast("Copied");
  } catch (_) {
    toast("Copy failed");
  }
}

let toastTimer;
function toast(message) {
  window.clearTimeout(toastTimer);
  els.toast.textContent = message;
  els.toast.classList.add("visible");
  toastTimer = window.setTimeout(() => {
    els.toast.classList.remove("visible");
  }, 2600);
}
