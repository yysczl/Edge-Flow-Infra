// ./node/asr/build/asr_node ./node/asr/models/zipformer
#include "StackFlow.h"
#include "asr_engine.h"
#include "channel.h"

#include <csignal>
#include <cstdint>
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
}

class AsrTask
{
public:
    explicit AsrTask(AsrEngine &engine) : engine_(engine)
    {
    }

    bool inference(
        const std::string &data,
        nlohmann::json &result,
        std::string &error)
    {
        try {
            const auto body = nlohmann::json::parse(data);
            const bool finish = body.value("finish", false);

            std::string text;
            bool endpoint = false;

            if (finish) {
                if (!engine_.finish(text)) {
                    error =
                        R"({"code":-11,"message":"ASR finish failed"})";
                    return false;
                }
                endpoint = true;
            } else {
                const auto samples =
                    body.at("samples").get<std::vector<int16_t>>();

                if (!engine_.feed(
                        samples.data(),
                        samples.size(),
                        text,
                        endpoint)) {
                    error =
                        R"({"code":-11,"message":"ASR inference failed"})";
                    return false;
                }
            }

            result = {
                {"text", text},
                {"endpoint", endpoint},
                {"final", finish || endpoint},
            };

            if (finish || endpoint) {
                engine_.reset();
            }
            return true;
        } catch (const std::exception &) {
            error =
                R"({"code":-2,"message":"data must contain PCM16 samples or finish=true"})";
            return false;
        }
    }

private:
    AsrEngine &engine_;
};

class AsrNode : public StackFlow
{
public:
    explicit AsrNode(AsrEngine &engine)
        : StackFlow("asr"), engine_(engine)
    {
    }

    int setup(
        const std::string &work_id,
        const std::string &,
        const std::string &) override
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
        auto task = std::make_shared<AsrTask>(engine_);

        channel->set_output(true);
        channel->set_stream(true);
        if (channel->subscriber_work_id(
                "",
                std::bind(
                    &AsrNode::on_inference,
                    this,
                    std::weak_ptr<AsrTask>(task),
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

    int exit(
        const std::string &work_id,
        const std::string &,
        const std::string &) override
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
        engine_.reset();
        send("None", "None", LLM_NO_ERROR, work_id);
        return 0;
    }

    void taskinfo(
        const std::string &work_id,
        const std::string &,
        const std::string &) override
    {
        nlohmann::json body = nlohmann::json::array();
        for (const auto &task : tasks_) {
            body.push_back(sample_get_work_id(task.first, unit_name_));
        }
        send("asr.tasklist", body, LLM_NO_ERROR, work_id);
    }

    ~AsrNode()
    {
        for (const auto &task : tasks_) {
            get_channel(task.first)->stop_subscriber("");
        }
        tasks_.clear();
    }

private:
    void on_inference(
        std::weak_ptr<AsrTask> task_weak,
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

        channel->send(
            "asr.result.stream",
            result,
            LLM_NO_ERROR,
            work_id);
    }

    AsrEngine &engine_;
    std::unordered_map<int, std::shared_ptr<AsrTask>> tasks_;
};

int main(int argc, char *argv[])
{
    if (argc != 2) {
        std::cerr << "Usage: " << argv[0] << " model_dir\n";
        return 1;
    }

    std::signal(SIGTERM, handle_signal);
    std::signal(SIGINT, handle_signal);

    AsrEngine engine;
    if (!engine.init(argv[1])) {
        return 1;
    }

    AsrNode node(engine);
    std::cout << "asr node started: ipc:///tmp/rpc.asr\n";

    while (!g_exit) {
        sleep(1);
    }

    return 0;
}
