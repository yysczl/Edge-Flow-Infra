import { reactive, ref } from "vue";
import { encodeWav, mergeFloat32, resampleFloat32 } from "../utils/audioWav";

export function useAudioRecorder() {
  const isRecording = ref(false);
  const activeTarget = ref("");
  const recordedFiles = reactive({
    asr: null,
    voice: null,
  });

  let recording = null;

  async function toggleRecording(target) {
    if (recording) {
      const file = await stopRecording(recording);
      recordedFiles[recording.target] = file;
      recording = null;
      isRecording.value = false;
      activeTarget.value = "";
      return file;
    }

    recording = await startRecording(target);
    isRecording.value = true;
    activeTarget.value = target;
    return null;
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
    const chunks = [];

    monitor.gain.value = 0;
    processor.onaudioprocess = (event) => {
      chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
    };

    source.connect(processor);
    processor.connect(monitor);
    monitor.connect(audioContext.destination);

    return {
      target,
      stream,
      audioContext,
      source,
      processor,
      monitor,
      chunks,
      sampleRate: audioContext.sampleRate,
    };
  }

  async function stopRecording(currentRecording) {
    currentRecording.processor.disconnect();
    currentRecording.monitor.disconnect();
    currentRecording.source.disconnect();
    currentRecording.stream.getTracks().forEach((track) => track.stop());
    await currentRecording.audioContext.close();

    const merged = mergeFloat32(currentRecording.chunks);
    const wav = encodeWav(resampleFloat32(merged, currentRecording.sampleRate, 16000), 16000);
    return new File([wav], "recording.wav", { type: "audio/wav" });
  }

  return {
    isRecording,
    activeTarget,
    recordedFiles,
    toggleRecording,
  };
}
