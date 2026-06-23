cmake_minimum_required(VERSION 3.12)
project(asr_node LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Threads REQUIRED)

set(REPO_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../..")
set(LOCAL_SHERPA_ROOT
    "${CMAKE_CURRENT_SOURCE_DIR}/third_party/sherpa-onnx")
set(DEMO_SHERPA_SOURCE
    "${REPO_ROOT}/single_node_demo/voice/sherpa-onnx")
set(DEMO_SHERPA_BUILD
    "${DEMO_SHERPA_SOURCE}/build-prebuilt")

set(SHERPA_INCLUDE_DIR "${LOCAL_SHERPA_ROOT}/include")
set(SHERPA_LIB_DIR "${LOCAL_SHERPA_ROOT}/lib")

set(ONNXRUNTIME_LIBRARY "${SHERPA_LIB_DIR}/libonnxruntime.a")
if(NOT EXISTS "${ONNXRUNTIME_LIBRARY}")
    set(ONNXRUNTIME_LIBRARY
        "${DEMO_SHERPA_BUILD}/_deps/onnxruntime-src/lib/libonnxruntime.a")
endif()

set(SHERPA_LIBRARIES
    "${SHERPA_LIB_DIR}/libsherpa-onnx-cxx-api.a"
    "${SHERPA_LIB_DIR}/libsherpa-onnx-c-api.a"
    "${SHERPA_LIB_DIR}/libsherpa-onnx-core.a"
    "${SHERPA_LIB_DIR}/libkaldi-native-fbank-core.a"
    "${SHERPA_LIB_DIR}/libkaldi-decoder-core.a"
    "${SHERPA_LIB_DIR}/libsherpa-onnx-kaldifst-core.a"
    "${SHERPA_LIB_DIR}/libssentencepiece_core.a"
    "${ONNXRUNTIME_LIBRARY}"
    "${SHERPA_LIB_DIR}/libsherpa-onnx-fstfar.a"
    "${SHERPA_LIB_DIR}/libsherpa-onnx-fst.a"
    # "${SHERPA_LIB_DIR}/libpiper_phonemize.a"
    # "${SHERPA_LIB_DIR}/libespeak-ng.a"
    # "${SHERPA_LIB_DIR}/libucd.a"
)

foreach(LIBRARY IN LISTS SHERPA_LIBRARIES)
    if(NOT EXISTS "${LIBRARY}")
        message(FATAL_ERROR "Missing ASR library: ${LIBRARY}")
    endif()
endforeach()

add_executable(asr_node
    src/main.cpp
    src/asr_engine.cpp
)

target_include_directories(asr_node PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/src"
    "${REPO_ROOT}/hybrid-comm/include"
    "${REPO_ROOT}/infra-controller/include"
    "${REPO_ROOT}/utils"
    "${SHERPA_INCLUDE_DIR}"
)

target_link_libraries(asr_node PRIVATE
    "${REPO_ROOT}/install/lib/libstackflow.a"
    zmq
    Threads::Threads
    "-Wl,--start-group"
    ${SHERPA_LIBRARIES}
    "-Wl,--end-group"
    m
    dl
)
