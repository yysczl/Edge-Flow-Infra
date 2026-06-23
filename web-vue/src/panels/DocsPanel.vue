<script setup>
import { computed, inject } from "vue";

const gateway = inject("gateway");

const displayBase = computed(() => {
  if (gateway.baseUrl.value) {
    return gateway.baseUrl.value;
  }
  return window.location.origin;
});

const examples = computed(() => ({
  health: `curl ${displayBase.value}/health`,
  models: `curl ${displayBase.value}/v1/models`,
  chat: `curl ${displayBase.value}/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -d '{"model":"${gateway.models.llm}","messages":[{"role":"user","content":"hello"}],"stream":false}'`,
  speech: `curl ${displayBase.value}/v1/audio/speech \\
  -H "Content-Type: application/json" \\
  -d '{"model":"${gateway.models.tts}","input":"hello","voice":"0","response_format":"wav","speed":1.0}' \\
  --output speech.wav`,
  transcribe: `curl ${displayBase.value}/v1/audio/transcriptions \\
  -F model=${gateway.models.asr} \\
  -F response_format=json \\
  -F file=@sample.wav`,
  conversation: `curl ${displayBase.value}/v1/audio/conversations \\
  -F file=@sample.wav \\
  -F model=${gateway.models.llm} \\
  -F voice=0 \\
  -F speed=1.0`,
}));

async function copyModelsCurl() {
  try {
    await navigator.clipboard.writeText(examples.value.models);
    gateway.toast("Copied");
  } catch (_) {
    gateway.toast("Copy failed");
  }
}
</script>

<template>
  <section class="panel">
    <div class="panel-header">
      <h2>API Docs</h2>
      <button type="button" @click="copyModelsCurl">
        Copy models curl
      </button>
    </div>

    <div class="docs-grid">
      <div class="endpoint-list">
        <h3>Endpoints</h3>
        <ul>
          <li><code>GET /health</code></li>
          <li><code>GET /v1/models</code></li>
          <li><code>POST /v1/chat/completions</code></li>
          <li><code>POST /v1/audio/speech</code></li>
          <li><code>POST /v1/audio/transcriptions</code></li>
          <li><code>POST /v1/audio/conversations</code></li>
        </ul>
      </div>

      <div class="snippet-list">
        <h3>OpenAI-compatible Examples</h3>
        <pre class="code-view">{{ examples.health }}</pre>
        <pre class="code-view">{{ examples.models }}</pre>
        <pre class="code-view">{{ examples.chat }}</pre>
        <pre class="code-view">{{ examples.speech }}</pre>
        <pre class="code-view">{{ examples.transcribe }}</pre>
        <pre class="code-view">{{ examples.conversation }}</pre>
      </div>
    </div>
  </section>
</template>
