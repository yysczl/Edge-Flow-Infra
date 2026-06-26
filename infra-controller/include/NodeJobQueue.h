#pragma once

#include <condition_variable>
#include <cstddef>
#include <mutex>
#include <queue>
#include <utility>

namespace StackFlows
{
template <typename Job>
class NodeJobQueue
{
public:
    explicit NodeJobQueue(std::size_t max_size)
        : max_size_(max_size)
    {
    }

    NodeJobQueue(const NodeJobQueue &) = delete;
    NodeJobQueue &operator=(const NodeJobQueue &) = delete;

    bool push(Job job)
    {
        {
            std::lock_guard<std::mutex> lock(mutex_);
            if (!running_ || jobs_.size() >= max_size_) {
                return false;
            }
            jobs_.push(std::move(job));
        }
        cv_.notify_one();
        return true;
    }

    bool wait_pop(Job &job)
    {
        std::unique_lock<std::mutex> lock(mutex_);
        cv_.wait(lock, [&] {
            return !jobs_.empty() || !running_;
        });

        if (jobs_.empty()) {
            return false;
        }

        job = std::move(jobs_.front());
        jobs_.pop();
        return true;
    }

    void stop()
    {
        {
            std::lock_guard<std::mutex> lock(mutex_);
            running_ = false;
        }
        cv_.notify_all();
    }

    std::size_t size() const
    {
        std::lock_guard<std::mutex> lock(mutex_);
        return jobs_.size();
    }

private:
    std::size_t max_size_;
    mutable std::mutex mutex_;
    std::condition_variable cv_;
    std::queue<Job> jobs_;
    bool running_ = true;
};
} // namespace StackFlows
