import { reactive } from "vue";
import { DEFAULT_MODELS, getHealth, getModels } from "../api/gateway";

export function useGatewayStatus(baseUrl) {
  const models = reactive({ ...DEFAULT_MODELS });
  const busy = reactive({
    llm: false,
    tts: false,
    asr: false,
  });
  const health = reactive({
    kind: "unknown",
    text: "Not checked",
    latency: "--",
    status: "Unknown",
    statusLatency: "--",
    unitManagerAddr: "--",
    payload: {},
  });

  async function refreshStatus() {
    setHealth("unknown", "Checking", "--");

    try {
      const { payload, elapsed } = await getHealth(baseUrl.value);
      setHealth("ok", payload.status || "ok", `${elapsed} ms`);
      renderHealth(payload, elapsed);
      await refreshModels();
    } catch (error) {
      setHealth("bad", "Offline", "--");
      health.status = "Offline";
      health.statusLatency = "--";
      health.unitManagerAddr = "--";
      health.payload = { error: error.message };
    }
  }

  async function refreshModels() {
    try {
      Object.assign(models, await getModels(baseUrl.value));
    } catch (_) {
      // Health remains useful even when model listing is temporarily unavailable.
    }
  }

  function setHealth(kind, text, latency) {
    health.kind = kind;
    health.text = text;
    health.latency = latency;
  }

  function renderHealth(payload, elapsed) {
    models.llm = payload.rkllm?.model || models.llm;
    models.tts = payload.tts?.model || models.tts;
    models.asr = payload.asr?.model || models.asr;

    busy.llm = Boolean(payload.rkllm?.busy);
    busy.tts = Boolean(payload.tts?.busy);
    busy.asr = Boolean(payload.asr?.busy);

    health.status = payload.status || "ok";
    health.statusLatency = `${elapsed} ms`;
    health.unitManagerAddr = `${payload.unit_manager?.host || "--"}:${payload.unit_manager?.port || "--"}`;
    health.payload = payload;
  }

  return {
    models,
    busy,
    health,
    refreshStatus,
    refreshModels,
  };
}
