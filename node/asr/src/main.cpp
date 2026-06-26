// ./node/asr/build/asr_node ./node/asr/models/zipformer
#include "StackFlow.h"
#include "asr_engine.h"
#include "channel.h"
#include "NodeJobQueue.h"
#include "NodeRuntimeUtil.h"

#include <csignal>
#include <cstdint>
#include <iostream>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
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
    explicit AsrTask(AsrEngine &engine)
        : engine_(engine), stream_(engine.create_stream())
    {
    }

    bool ready() const
    {
        return static_cast<bool>(stream_);
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
                if (!engine_.finish(stream_, text)) {
                    error =
                        R"({"code":-11,"message":"ASR finish failed"})";
                    return false;
                }
                endpoint = true;
            } else {
                const auto samples =
                    body.at("samples").get<std::vector<int16_t>>();

                if (!engine_.feed(
                        stream_,
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
                engine_.reset(stream_);
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
    AsrEngine::StreamPtr stream_;
};

class AsrNode : public StackFlow
{
public:
    explicit AsrNode(AsrEngine &engine)
        : StackFlow("asr"),
          engine_(engine),
          max_sessions_(read_size_env("ASR_MAX_SESSIONS", 8)),
          max_queue_size_(read_size_env("ASR_MAX_QUEUE_SIZE", 256)),
          jobs_(max_queue_size_)
    {
        worker_ = std::thread(&AsrNode::worker_loop, this);
    }

    int setup(
        const std::string &work_id,
        const std::string &,
        const std::string &) override
    {
        {
            std::lock_guard<std::mutex> lock(tasks_mutex_);
            if (tasks_.size() >= max_sessions_) {
                send(
                    "None",
                    "None",
                    R"({"code":-21,"message":"session full"})",
                    work_id);
                return -1;
            }
        }

        const int work_id_num = sample_get_work_id_num(work_id);
        auto channel = get_channel(work_id);
        auto task = std::make_shared<AsrTask>(engine_);
        if (!task->ready()) {
            send(
                "None",
                "None",
                R"({"code":-11,"message":"create ASR stream failed"})",
                work_id);
            return -1;
        }

        channel->set_output(true);
        channel->set_stream(true);
        if (channel->subscriber_work_id(
                "",
                std::bind(
                    // 每次客户端发送一块 PCM 数据，on_inference 就被触发
                    &AsrNode::on_inference, // 每收到数据就触发一次
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

        {
            std::lock_guard<std::mutex> lock(tasks_mutex_);
            if (tasks_.size() >= max_sessions_) {
                channel->stop_subscriber("");
                send(
                    "None",
                    "None",
                    R"({"code":-21,"message":"session full"})",
                    work_id);
                return -1;
            }
            tasks_[work_id_num] = task;
        }
        send("None", "None", LLM_NO_ERROR, work_id);
        return 0;
    }

    int exit(
        const std::string &work_id,
        const std::string &,
        const std::string &) override
    {
        const int work_id_num = sample_get_work_id_num(work_id);
        {
            std::lock_guard<std::mutex> lock(tasks_mutex_);
            const auto it = tasks_.find(work_id_num);
            if (it == tasks_.end()) {
                send(
                    "None",
                    "None",
                    R"({"code":-6,"message":"Unit Does Not Exist"})",
                    work_id);
                return -1;
            }
            tasks_.erase(it);
        }

        get_channel(work_id_num)->stop_subscriber("");
        send("None", "None", LLM_NO_ERROR, work_id);
        return 0;
    }

    void taskinfo(
        const std::string &work_id,
        const std::string &,
        const std::string &) override
    {
        nlohmann::json body = nlohmann::json::array();
        {
            std::lock_guard<std::mutex> lock(tasks_mutex_);
            for (const auto &task : tasks_) {
                body.push_back(sample_get_work_id(task.first, unit_name_));
            }
        }
        send("asr.tasklist", body, LLM_NO_ERROR, work_id);
    }

    ~AsrNode()
    {
        stop_worker();
        {
            std::lock_guard<std::mutex> lock(tasks_mutex_);
            for (const auto &task : tasks_) {
                get_channel(task.first)->stop_subscriber("");
            }
            tasks_.clear();
        }
    }

private:
    struct Job {
        std::weak_ptr<AsrTask> task;
        std::weak_ptr<llm_channel_obj> channel;
        std::string work_id;
        std::string request_id;
        std::string input;
    };

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

        enqueue_job({task_weak, channel_weak, work_id, channel->request_id_, data}, channel);
    }

    void enqueue_job(Job job, const std::shared_ptr<llm_channel_obj> &channel)
    {
        const std::string work_id = job.work_id;
        if (!jobs_.push(std::move(job))) {
            channel->send(
                "None",
                "None",
                R"({"code":-22,"message":"queue full"})",
                work_id);
        }
    }

    void worker_loop()
    {
        Job job;
        while (jobs_.wait_pop(job)) {
            auto task = job.task.lock();
            auto channel = job.channel.lock();
            if (!task || !channel) {
                continue;
            }

            channel->request_id_ = job.request_id;

            nlohmann::json result;
            std::string error;
            if (!task->inference(job.input, result, error)) {
                channel->send("None", "None", error, job.work_id);
                continue;
            }

            channel->send(
                "asr.result.stream",
                result,
                LLM_NO_ERROR,
                job.work_id);
        }
    }

    void stop_worker()
    {
        jobs_.stop();
        if (worker_.joinable()) {
            worker_.join();
        }
    }

    AsrEngine &engine_;
    std::unordered_map<int, std::shared_ptr<AsrTask>> tasks_;
    std::size_t max_sessions_;
    std::size_t max_queue_size_;
    std::mutex tasks_mutex_;
    NodeJobQueue<Job> jobs_;
    std::thread worker_;
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
