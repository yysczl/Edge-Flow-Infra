/*
cd /home/pi/Edge-LLM-Infra/node/tts
cmake -S . -B build
cmake --build build -j12

./build/tts_node ./models/single_speaker_fast.bin plughw:1,0
*/

#include "StackFlow.h"
#include "channel.h"
#include "tts_engine.h"

#include <atomic>
#include <csignal>
#include <iostream>
#include <memory>
#include <string>
#include <unordered_map>
#include <vector>
#include <unistd.h>

using namespace StackFlows;

namespace
{
volatile std::sig_atomic_t g_exit = 0;

void handle_signal(int)
{
    g_exit = 1;
}

std::string base64_encode(const std::vector<uint8_t> &bytes)
{
    static constexpr char alphabet[] =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

    std::string out;
    out.reserve(((bytes.size() + 2) / 3) * 4);

    size_t index = 0;
    while (index + 3 <= bytes.size()) {
        const uint32_t value =
            (static_cast<uint32_t>(bytes[index]) << 16) |
            (static_cast<uint32_t>(bytes[index + 1]) << 8) |
            static_cast<uint32_t>(bytes[index + 2]);
        out.push_back(alphabet[(value >> 18) & 0x3f]);
        out.push_back(alphabet[(value >> 12) & 0x3f]);
        out.push_back(alphabet[(value >> 6) & 0x3f]);
        out.push_back(alphabet[value & 0x3f]);
        index += 3;
    }

    const size_t remaining = bytes.size() - index;
    if (remaining == 1) {
        const uint32_t value = static_cast<uint32_t>(bytes[index]) << 16;
        out.push_back(alphabet[(value >> 18) & 0x3f]);
        out.push_back(alphabet[(value >> 12) & 0x3f]);
        out.push_back('=');
        out.push_back('=');
    } else if (remaining == 2) {
        const uint32_t value =
            (static_cast<uint32_t>(bytes[index]) << 16) |
            (static_cast<uint32_t>(bytes[index + 1]) << 8);
        out.push_back(alphabet[(value >> 18) & 0x3f]);
        out.push_back(alphabet[(value >> 12) & 0x3f]);
        out.push_back(alphabet[(value >> 6) & 0x3f]);
        out.push_back('=');
    }

    return out;
}
} // namespace

class TtsTask
{
public:
    explicit TtsTask(TtsEngine &engine) : engine_(engine)
    {
    }

    bool inference(const std::string &data, nlohmann::json &result, std::string &error)
    {
        std::string text;
        std::string format = "play";
        int32_t speaker_id = 0;
        float length_scale = 1.0f;
        bool play = true;

        try {
            const auto body = nlohmann::json::parse(data);
            if (body.is_string()) {
                text = body.get<std::string>();
            } else {
                text = body.value("text", "");
                if (text.empty()) {
                    text = body.value("delta", "");
                }
                format = body.value("format", body.value("response_format", format));
                play = body.value("play", play);
                speaker_id = body.value("speaker_id", 0);
                length_scale = body.value("length_scale", body.value("speed", 1.0f));
            }
        } catch (const std::exception &) {
            text = data;
        }

        if (!play && format == "wav") {
            std::vector<uint8_t> wav;
            int32_t sample_count = 0;
            if (!engine_.synthesize_to_wav(text, speaker_id, length_scale, wav, sample_count, error)) {
                return false;
            }

            result = {
                {"text", text},
                {"sample_rate", TtsEngine::sample_rate()},
                {"samples", sample_count},
                {"speaker_id", speaker_id},
                {"length_scale", length_scale},
                {"format", "wav"},
                {"audio_base64", base64_encode(wav)},
                {"played", false},
            };
            return true;
        }

        std::vector<int16_t> pcm;
        if (!engine_.synthesize_to_pcm(text, speaker_id, length_scale, pcm, error)) {
            return false;
        }

        if (!engine_.play_audio(pcm, error)) {
            return false;
        }

        result = {
            {"text", text},
            {"sample_rate", TtsEngine::sample_rate()},
            {"samples", static_cast<int32_t>(pcm.size())},
            {"speaker_id", speaker_id},
            {"length_scale", length_scale},
            {"format", "pcm"},
            {"played", true},
        };
        return true;
    }

private:
    TtsEngine &engine_;
};

class TtsNode : public StackFlow
{
public:
    explicit TtsNode(TtsEngine &engine) : StackFlow("tts"), engine_(engine)
    {
    }

    int setup(const std::string &work_id, const std::string &, const std::string &) override
    {
        if (!tasks_.empty()) {
            send(
                "None",
                "None",
                R"({"code":-21,"message":"task full"})",
                work_id);
            return -1;
        }

        const int work_id_num = sample_get_work_id_num(work_id);
        auto channel = get_channel(work_id);
        auto task = std::make_shared<TtsTask>(engine_);

        channel->set_output(true);
        channel->set_stream(false);
        if (channel->subscriber_work_id(
                "",
                std::bind(
                    &TtsNode::on_inference,
                    this,
                    std::weak_ptr<TtsTask>(task),
                    std::weak_ptr<llm_channel_obj>(channel),
                    work_id,
                    std::placeholders::_1,
                    std::placeholders::_2)) != 0) {
            send(
                "None",
                "None",
                R"({"code":-11,"message":"subscribe failed"})",
                work_id);
            return -1;
        }

        tasks_[work_id_num] = task;
        send("None", "None", LLM_NO_ERROR, work_id);
        return 0;
    }

    int exit(const std::string &work_id, const std::string &, const std::string &) override
    {
        const int work_id_num = sample_get_work_id_num(work_id);
        const auto it = tasks_.find(work_id_num);
        if (it == tasks_.end()) {
            send(
                "None",
                "None",
                R"({"code":-6,"message":"Unit Does Not Exist"})",
                work_id);
            return -1;
        }

        get_channel(work_id_num)->stop_subscriber("");
        tasks_.erase(it);
        send("None", "None", LLM_NO_ERROR, work_id);
        return 0;
    }

    void taskinfo(const std::string &work_id, const std::string &, const std::string &) override
    {
        nlohmann::json body;
        body["tasks"] = nlohmann::json::array();
        for (const auto &task : tasks_) {
            body["tasks"].push_back(sample_get_work_id(task.first, unit_name_));
        }
        body["sample_rate"] = 16000;
        body["speaker_count"] = engine_.speaker_count();
        send("tts.taskinfo", body, LLM_NO_ERROR, work_id);
    }

    ~TtsNode()
    {
        for (const auto &task : tasks_) {
            get_channel(task.first)->stop_subscriber("");
        }
        tasks_.clear();
    }

private:
    void on_inference(
        std::weak_ptr<TtsTask> task_weak,
        std::weak_ptr<llm_channel_obj> channel_weak,
        const std::string &work_id,
        const std::string &,
        const std::string &data)
    {
        auto task = task_weak.lock();
        auto channel = channel_weak.lock();
        if (!task || !channel) {
            return;
        }

        nlohmann::json result;
        std::string error;
        if (!task->inference(data, result, error)) {
            channel->send("None", "None", error, work_id);
            return;
        }

        const std::string object_name =
            result.value("played", true) ? "tts.play.done" : "tts.audio";
        channel->send(object_name, result, LLM_NO_ERROR, work_id);
    }

    TtsEngine &engine_;
    std::unordered_map<int, std::shared_ptr<TtsTask>> tasks_;
};

int main(int argc, char *argv[])
{
    if (argc < 2 || argc > 3) {
        std::cerr << "Usage: " << argv[0] << " model.bin [alsa_device]\n";
        return 1;
    }

    std::signal(SIGTERM, handle_signal);
    std::signal(SIGINT, handle_signal);

    const std::string alsa_device = argc >= 3 ? argv[2] : "default";

    TtsEngine engine;
    if (!engine.init(argv[1], alsa_device)) {
        std::cerr << "Failed to initialize TTS engine: " << argv[1] << '\n';
        return 1;
    }

    TtsNode node(engine);
    std::cout << "tts node started: ipc:///tmp/rpc.tts"
              << " alsa_device=" << alsa_device << '\n';
    while (!g_exit) {
        sleep(1);
    }
    return 0;
}
