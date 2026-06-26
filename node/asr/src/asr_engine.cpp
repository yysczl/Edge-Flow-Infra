#include "asr_engine.h"

#include <iostream>
#include <utility>
#include <vector>

namespace
{
constexpr int32_t kSampleRate = 16000;
}

bool AsrEngine::init(const std::string &model_dir)
{
    sherpa_onnx::cxx::OnlineRecognizerConfig config;
    config.model_config.transducer.encoder =
        model_dir + "/encoder-epoch-99-avg-1.int8.onnx";
    config.model_config.transducer.decoder =
        model_dir + "/decoder-epoch-99-avg-1.onnx";
    config.model_config.transducer.joiner =
        model_dir + "/joiner-epoch-99-avg-1.int8.onnx";
    config.model_config.tokens = model_dir + "/tokens.txt";
    config.model_config.num_threads = 4;
    config.model_config.provider = "cpu";
    config.model_config.model_type = "zipformer";
    config.feat_config.sample_rate = kSampleRate;
    config.decoding_method = "greedy_search";
    config.enable_endpoint = true;

    auto recognizer =
        sherpa_onnx::cxx::OnlineRecognizer::Create(config);
    if (!recognizer.Get()) {
        std::cerr << "Failed to initialize ASR model: "
                  << model_dir << '\n';
        return false;
    }

    shutdown();
    recognizer_ =
        std::make_unique<sherpa_onnx::cxx::OnlineRecognizer>(
            std::move(recognizer));
    return true;
}

AsrEngine::StreamPtr AsrEngine::create_stream()
{
    std::lock_guard<std::mutex> lock(mutex_);
    if (!recognizer_) {
        return nullptr;
    }

    auto stream = recognizer_->CreateStream();
    if (!stream.Get()) {
        return nullptr;
    }

    return std::make_unique<sherpa_onnx::cxx::OnlineStream>(
        std::move(stream));
}

bool AsrEngine::feed(
    StreamPtr &stream,
    const int16_t *samples,
    std::size_t sample_count,
    std::string &text,
    bool &endpoint)
{
    std::lock_guard<std::mutex> lock(mutex_);
    if (!recognizer_ || !stream ||
        (!samples && sample_count != 0)) {
        return false;
    }

    std::vector<float> input(sample_count);
    for (std::size_t i = 0; i < sample_count; ++i) {
        input[i] = static_cast<float>(samples[i]) / 32768.0f;
    }

    if (!input.empty()) {
        stream->AcceptWaveform(
            kSampleRate,
            input.data(),
            static_cast<int32_t>(input.size()));
    }

    while (recognizer_->IsReady(stream.get())) {
        recognizer_->Decode(stream.get());
    }

    text = recognizer_->GetResult(stream.get()).text;
    endpoint = recognizer_->IsEndpoint(stream.get());
    return true;
}

bool AsrEngine::finish(StreamPtr &stream, std::string &text)
{
    std::lock_guard<std::mutex> lock(mutex_);
    if (!recognizer_ || !stream) {
        return false;
    }

    stream->InputFinished();
    while (recognizer_->IsReady(stream.get())) {
        recognizer_->Decode(stream.get());
    }

    text = recognizer_->GetResult(stream.get()).text;
    return true;
}

void AsrEngine::reset(StreamPtr &stream)
{
    std::lock_guard<std::mutex> lock(mutex_);
    if (!recognizer_) {
        return;
    }

    stream.reset();
    auto next_stream = recognizer_->CreateStream();
    if (next_stream.Get()) {
        stream =
            std::make_unique<sherpa_onnx::cxx::OnlineStream>(
                std::move(next_stream));
    }
}

void AsrEngine::shutdown()
{
    std::lock_guard<std::mutex> lock(mutex_);
    recognizer_.reset();
}

AsrEngine::~AsrEngine()
{
    shutdown();
}
