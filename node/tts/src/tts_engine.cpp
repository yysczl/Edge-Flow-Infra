#include "tts_engine.h"

#include "SynthesizerTrn.h"
#include "utils.h"

#include <cstring>
#include <utility>
#include <vector>

namespace
{
void append_u16_le(std::vector<uint8_t> &buffer, uint16_t value)
{
    buffer.push_back(static_cast<uint8_t>(value & 0xff));
    buffer.push_back(static_cast<uint8_t>((value >> 8) & 0xff));
}

void append_u32_le(std::vector<uint8_t> &buffer, uint32_t value)
{
    buffer.push_back(static_cast<uint8_t>(value & 0xff));
    buffer.push_back(static_cast<uint8_t>((value >> 8) & 0xff));
    buffer.push_back(static_cast<uint8_t>((value >> 16) & 0xff));
    buffer.push_back(static_cast<uint8_t>((value >> 24) & 0xff));
}

void append_bytes(std::vector<uint8_t> &buffer, const char *data, size_t size)
{
    buffer.insert(buffer.end(), data, data + size);
}
}  // namespace

bool TtsEngine::init(const std::string &model_path, const std::string &alsa_device)
{
    std::lock_guard<std::mutex> lock(mutex_);
    shutdown();
    alsa_device_ = alsa_device.empty() ? "default" : alsa_device;

    std::vector<char> model_path_copy(model_path.begin(), model_path.end());
    model_path_copy.push_back('\0');

    model_size_ = ttsLoadModel(model_path_copy.data(), &model_data_);
    if (model_size_ <= 0 || model_data_ == nullptr) {
        model_data_ = nullptr;
        model_size_ = 0;
        return false;
    }

    synthesizer_ = std::make_unique<SynthesizerTrn>(model_data_, model_size_);

    return true;
}

bool TtsEngine::synthesize_and_play(
    const std::string &text,
    int32_t speaker_id,
    float length_scale,
    int32_t &sample_count,
    std::string &error)
{
    std::lock_guard<std::mutex> lock(mutex_);
    sample_count = 0;

    std::vector<int16_t> pcm;
    if (!synthesize_to_pcm_locked(text, speaker_id, length_scale, pcm, error)) {
        return false;
    }

    sample_count = static_cast<int32_t>(pcm.size());
    return play_pcm_locked(pcm.data(), sample_count, error);
}

bool TtsEngine::synthesize_to_pcm(
    const std::string &text,
    int32_t speaker_id,
    float length_scale,
    std::vector<int16_t> &pcm,
    std::string &error)
{
    std::lock_guard<std::mutex> lock(mutex_);
    return synthesize_to_pcm_locked(text, speaker_id, length_scale, pcm, error);
}

bool TtsEngine::synthesize_to_wav(
    const std::string &text,
    int32_t speaker_id,
    float length_scale,
    std::vector<uint8_t> &wav,
    int32_t &sample_count,
    std::string &error)
{
    std::vector<int16_t> pcm;
    if (!synthesize_to_pcm(text, speaker_id, length_scale, pcm, error)) {
        sample_count = 0;
        wav.clear();
        return false;
    }

    sample_count = static_cast<int32_t>(pcm.size());
    write_wav(pcm, wav);
    return true;
}

bool TtsEngine::play_audio(
    const int16_t *samples,
    int32_t sample_count,
    std::string &error)
{
    std::lock_guard<std::mutex> lock(mutex_);
    return play_pcm_locked(samples, sample_count, error);
}

bool TtsEngine::play_audio(
    const std::vector<int16_t> &pcm,
    std::string &error)
{
    return play_audio(pcm.data(), static_cast<int32_t>(pcm.size()), error);
}

bool TtsEngine::synthesize_to_pcm_locked(
    const std::string &text,
    int32_t speaker_id,
    float length_scale,
    std::vector<int16_t> &pcm,
    std::string &error)
{
    pcm.clear();
    if (!synthesizer_) {
        error = R"({"code":-11,"message":"TTS model is not initialized"})";
        return false;
    }
    if (text.empty()) {
        error = R"({"code":-24,"message":"text is empty"})";
        return false;
    }
    if (length_scale <= 0.0f) {
        error = R"({"code":-2,"message":"length_scale must be positive"})";
        return false;
    }

    int32_t sample_count = 0;
    int16_t *audio = synthesizer_->infer(text, speaker_id, length_scale, sample_count);
    if (audio == nullptr || sample_count <= 0) {
        error = R"({"code":-11,"message":"TTS inference failed"})";
        return false;
    }

    pcm.assign(audio, audio + sample_count);
    tts_free_data(audio);
    return true;
}

int32_t TtsEngine::speaker_count() const
{
    std::lock_guard<std::mutex> lock(mutex_);
    if (!synthesizer_) {
        return 0;
    }
    return synthesizer_->getSpeakerNum();
}

bool TtsEngine::play_pcm_locked(const int16_t *samples, int32_t sample_count, std::string &error)
{
    if (samples == nullptr || sample_count <= 0) {
        error = R"({"code":-24,"message":"audio samples are empty"})";
        return false;
    }

    if (!pcm_handle_) {
        const int open_err = snd_pcm_open(&pcm_handle_, alsa_device_.c_str(), SND_PCM_STREAM_PLAYBACK, 0);
        if (open_err < 0) {
            error = std::string(R"({"code":-11,"message":"ALSA open failed for device )") +
                    alsa_device_ + ": " + snd_strerror(open_err) + R"("})";
            return false;
        }
    }

    int err = snd_pcm_set_params(
        pcm_handle_,
        SND_PCM_FORMAT_S16_LE,
        SND_PCM_ACCESS_RW_INTERLEAVED,
        1,
        kSampleRate,
        1,
        50000);
    if (err < 0) {
        error = std::string(R"({"code":-11,"message":"ALSA set params failed: )") +
                snd_strerror(err) + R"("})";
        return false;
    }

    snd_pcm_uframes_t frames_written = 0;
    const snd_pcm_uframes_t total_frames = static_cast<snd_pcm_uframes_t>(sample_count);
    while (frames_written < total_frames) {
        const snd_pcm_sframes_t ret = snd_pcm_writei(
            pcm_handle_,
            samples + frames_written,
            total_frames - frames_written);
        if (ret == -EPIPE) {
            snd_pcm_prepare(pcm_handle_);
            continue;
        }
        if (ret < 0) {
            err = snd_pcm_recover(pcm_handle_, static_cast<int>(ret), 1);
            if (err < 0) {
                error = std::string(R"({"code":-11,"message":"ALSA write failed: )") +
                        snd_strerror(static_cast<int>(ret)) + R"("})";
                return false;
            }
            continue;
        }
        frames_written += static_cast<snd_pcm_uframes_t>(ret);
    }

    snd_pcm_drain(pcm_handle_);
    return true;
}

void TtsEngine::write_wav(
    const std::vector<int16_t> &pcm,
    std::vector<uint8_t> &wav)
{
    static constexpr uint16_t kChannels = 1;
    static constexpr uint16_t kBitsPerSample = 16;
    static constexpr uint16_t kBlockAlign = kChannels * kBitsPerSample / 8;
    static constexpr uint32_t kByteRate = kSampleRate * kBlockAlign;

    const uint32_t data_size = static_cast<uint32_t>(pcm.size() * sizeof(int16_t));
    const uint32_t riff_size = 36 + data_size;

    wav.clear();
    wav.reserve(44 + data_size);
    append_bytes(wav, "RIFF", 4);
    append_u32_le(wav, riff_size);
    append_bytes(wav, "WAVE", 4);
    append_bytes(wav, "fmt ", 4);
    append_u32_le(wav, 16);
    append_u16_le(wav, 1);
    append_u16_le(wav, kChannels);
    append_u32_le(wav, kSampleRate);
    append_u32_le(wav, kByteRate);
    append_u16_le(wav, kBlockAlign);
    append_u16_le(wav, kBitsPerSample);
    append_bytes(wav, "data", 4);
    append_u32_le(wav, data_size);

    for (const int16_t sample : pcm) {
        append_u16_le(wav, static_cast<uint16_t>(sample));
    }
}

void TtsEngine::shutdown()
{
    synthesizer_.reset();
    if (pcm_handle_) {
        snd_pcm_close(pcm_handle_);
        pcm_handle_ = nullptr;
    }
    if (model_data_) {
        tts_free_data(model_data_);
        model_data_ = nullptr;
        model_size_ = 0;
    }
}

TtsEngine::~TtsEngine()
{
    std::lock_guard<std::mutex> lock(mutex_);
    shutdown();
}
