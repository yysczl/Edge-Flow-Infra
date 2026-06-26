#pragma once

#include <cstddef>
#include <cstdlib>
#include <exception>
#include <string>

namespace StackFlows
{
inline std::size_t read_size_env(const char *name, std::size_t fallback)
{
    const char *value = std::getenv(name);
    if (!value || !*value) {
        return fallback;
    }

    try {
        const auto parsed = std::stoull(value);
        return parsed > 0 ? static_cast<std::size_t>(parsed) : fallback;
    } catch (const std::exception &) {
        return fallback;
    }
}
} // namespace StackFlows
