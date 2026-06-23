/*
 * SPDX-FileCopyrightText: 2024 M5Stack Technology CO LTD
 *
 * SPDX-License-Identifier: MIT
 */
#include <fstream>
#include <iostream>
#include <limits.h>
#include <string>
#include <unistd.h>
#include <vector>

#include "all.h"
#include "json.hpp"

namespace
{
std::string executable_dir()
{
    char path[PATH_MAX] = {0};
    ssize_t size = readlink("/proc/self/exe", path, sizeof(path) - 1);
    if (size <= 0) {
        return "";
    }
    path[size] = '\0';

    std::string exe_path(path);
    const auto slash = exe_path.find_last_of('/');
    if (slash == std::string::npos) {
        return "";
    }
    return exe_path.substr(0, slash);
}

bool load_config_file(const std::string &path, nlohmann::json &config)
{
    std::ifstream file(path);
    if (!file.is_open()) {
        return false;
    }

    try {
        file >> config;
    } catch (...) {
        return false;
    }
    return true;
}
}  // namespace

void load_default_config()
{
    nlohmann::json req_body;

    const std::string exe_dir = executable_dir();
    const std::vector<std::string> candidates = {
        exe_dir + "/../master_config.json",
        exe_dir + "/master_config.json",
        "unit-manager/master_config.json",
        "../master_config.json",
    };

    bool loaded = false;
    for (const auto &path : candidates) {
        if (load_config_file(path, req_body)) {
            loaded = true;
            break;
        }
    }

    if (!loaded) {
        ALOGE("failed to load master_config.json");
        return;
    }

    for (auto it = req_body.begin(); it != req_body.end(); ++it) {
        if (req_body[it.key()].is_number()) {
            key_sql[(std::string)it.key()] = (int)it.value();
        }
        if (req_body[it.key()].is_string()) {
            key_sql[(std::string)it.key()] = (std::string)it.value();
        }
    }
}
