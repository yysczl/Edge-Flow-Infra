#pragma once

#include <alsa/asoundlib.h>
#include <cstdint>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

#include "SynthesizerTrn.h"

class TtsEngine
{
public:
    ~TtsEngine();

    bool init(const std::string &model_path, const std::string &alsa_device);
    bool synthesize_and_play(
        const std::string &text,
        int32_t speaker_id,
        float length_scale,
        int32_t &sample_count,
        std::string &error);
    bool synthesize_to_pcm(
        const std::string &text,
        int32_t speaker_id,
        float length_scale,
        std::vector<int16_t> &pcm,
        std::string &error);
    bool synthesize_to_wav(
        const std::string &text,
        int32_t speaker_id,
        float length_scale,
        std::vector<uint8_t> &wav,
        int32_t &sample_count,
        std::string &error);
    bool play_audio(
        const int16_t *samples,
        int32_t sample_count,
        std::string &error);
    bool play_audio(
        const std::vector<int16_t> &pcm,
        std::string &error);
    int32_t speaker_count() const;
    static constexpr unsigned int sample_rate()
    {
        return kSampleRate;
    }
    void shutdown();

private:
    bool synthesize_to_pcm_locked(
        const std::string &text,
        int32_t speaker_id,
        float length_scale,
        std::vector<int16_t> &pcm,
        std::string &error);
    bool play_pcm_locked(const int16_t *samples, int32_t sample_count, std::string &error);
    static void write_wav(
        const std::vector<int16_t> &pcm,
        std::vector<uint8_t> &wav);

    static constexpr unsigned int kSampleRate = 16000;

    mutable std::mutex mutex_;
    float *model_data_ = nullptr;
    int32_t model_size_ = 0;
    std::string alsa_device_ = "default";
    std::unique_ptr<SynthesizerTrn> synthesizer_;
    snd_pcm_t *pcm_handle_ = nullptr;
};
