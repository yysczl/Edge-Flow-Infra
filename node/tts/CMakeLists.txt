cmake_minimum_required(VERSION 3.12)
project(tts_node LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O3 -fopenmp")
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -O3 -fopenmp")

find_package(Threads REQUIRED)

set(REPO_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../..")
set(SUMMER_TTS_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/summer_tts")
set(EIGEN_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/third_party/eigen-3.4.0")

file(GLOB SUMMER_TTS_ENGIPA_SRC "${SUMMER_TTS_ROOT}/src/engipa/*.cpp")
file(GLOB SUMMER_TTS_HZ2PY_SRC "${SUMMER_TTS_ROOT}/src/hz2py/*.cpp")
file(GLOB SUMMER_TTS_NN_OP_SRC "${SUMMER_TTS_ROOT}/src/nn_op/*.cpp")
file(GLOB SUMMER_TTS_PLATFORM_SRC "${SUMMER_TTS_ROOT}/src/platform/*.cpp")
file(GLOB SUMMER_TTS_UTILS_SRC "${SUMMER_TTS_ROOT}/src/utils/*.cpp")
file(GLOB SUMMER_TTS_MODULES_SRC "${SUMMER_TTS_ROOT}/src/modules/*.cpp")
file(GLOB SUMMER_TTS_MODELS_SRC "${SUMMER_TTS_ROOT}/src/models/*.cpp")

set(SUMMER_TTS_TN_SRC
    "${SUMMER_TTS_ROOT}/src/tn/glog/src/demangle.cc"
    "${SUMMER_TTS_ROOT}/src/tn/glog/src/logging.cc"
    "${SUMMER_TTS_ROOT}/src/tn/glog/src/raw_logging.cc"
    "${SUMMER_TTS_ROOT}/src/tn/glog/src/symbolize.cc"
    "${SUMMER_TTS_ROOT}/src/tn/glog/src/utilities.cc"
    "${SUMMER_TTS_ROOT}/src/tn/glog/src/vlog_is_on.cc"
    "${SUMMER_TTS_ROOT}/src/tn/glog/src/signalhandler.cc"
    "${SUMMER_TTS_ROOT}/src/tn/gflags/src/gflags.cc"
    "${SUMMER_TTS_ROOT}/src/tn/gflags/src/gflags_reporting.cc"
    "${SUMMER_TTS_ROOT}/src/tn/gflags/src/gflags_completions.cc"
    "${SUMMER_TTS_ROOT}/src/tn/openfst/src/lib/compat.cc"
    "${SUMMER_TTS_ROOT}/src/tn/openfst/src/lib/flags.cc"
    "${SUMMER_TTS_ROOT}/src/tn/openfst/src/lib/fst.cc"
    "${SUMMER_TTS_ROOT}/src/tn/openfst/src/lib/fst-types.cc"
    "${SUMMER_TTS_ROOT}/src/tn/openfst/src/lib/mapped-file.cc"
    "${SUMMER_TTS_ROOT}/src/tn/openfst/src/lib/properties.cc"
    "${SUMMER_TTS_ROOT}/src/tn/openfst/src/lib/symbol-table.cc"
    "${SUMMER_TTS_ROOT}/src/tn/openfst/src/lib/symbol-table-ops.cc"
    "${SUMMER_TTS_ROOT}/src/tn/openfst/src/lib/util.cc"
    "${SUMMER_TTS_ROOT}/src/tn/openfst/src/lib/weight.cc"
    "${SUMMER_TTS_ROOT}/src/tn/processor.cc"
    "${SUMMER_TTS_ROOT}/src/tn/token_parser.cc"
    "${SUMMER_TTS_ROOT}/src/tn/utf8_string.cc")

add_executable(tts_node
    src/main.cpp
    src/tts_engine.cpp
    ${SUMMER_TTS_TN_SRC}
    ${SUMMER_TTS_ENGIPA_SRC}
    ${SUMMER_TTS_HZ2PY_SRC}
    ${SUMMER_TTS_NN_OP_SRC}
    ${SUMMER_TTS_PLATFORM_SRC}
    ${SUMMER_TTS_UTILS_SRC}
    ${SUMMER_TTS_MODULES_SRC}
    ${SUMMER_TTS_MODELS_SRC}
)

target_include_directories(tts_node PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/src"
    "${REPO_ROOT}/hybrid-comm/include"
    "${REPO_ROOT}/infra-controller/include"
    "${REPO_ROOT}/utils"
    "${EIGEN_ROOT}"
    "${SUMMER_TTS_ROOT}/src/tn/header"
    "${SUMMER_TTS_ROOT}/include"
    "${SUMMER_TTS_ROOT}/src/header"
)

target_link_libraries(tts_node PRIVATE
    "${REPO_ROOT}/install/lib/libstackflow.a"
    zmq
    asound
    Threads::Threads
)
