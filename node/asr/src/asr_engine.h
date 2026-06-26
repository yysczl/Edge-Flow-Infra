#pragma once

#include <cstddef>
#include <cstdint>
#include <memory>
#include <mutex>
#include <string>

#include "sherpa-onnx/c-api/cxx-api.h"

class AsrEngine
{
public:
    using StreamPtr =
        std::unique_ptr<sherpa_onnx::cxx::OnlineStream>;

    ~AsrEngine();

    bool init(const std::string &model_dir);
    StreamPtr create_stream();

    bool feed(
        StreamPtr &stream,
        const int16_t *samples,
        std::size_t sample_count,
        std::string &text,
        bool &endpoint);

    bool finish(StreamPtr &stream, std::string &text);
    void reset(StreamPtr &stream);
    void shutdown();

private:
    std::unique_ptr<sherpa_onnx::cxx::OnlineRecognizer> recognizer_;
    std::mutex mutex_;
};
