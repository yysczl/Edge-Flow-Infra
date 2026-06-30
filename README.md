# Edge-Flow-Infra

Edge-Flow-Infra 是一个面向边缘设备的本地 AI 推理基础设施项目。项目将
C++ 分布式任务调度框架、ZMQ 节点间通信、OpenAI 兼容 FastAPI 网关和
Vue 3 控制台组合在一起，用于在本地运行 LLM、ASR、TTS 推理节点，并通过
标准 HTTP API 对外提供能力。

当前项目支持：

- 本地 RKLLM 聊天补全，支持流式输出。
- 本地 ASR 语音转写，输入格式为 16 kHz 单声道 PCM16 WAV。
- 本地 TTS 语音合成，输出 WAV 音频。
- ASR -> LLM -> TTS 语音对话闭环。
- 通过 `unit-manager` 实现 TCP/ZMQ 协议桥接。
- Web 控制台，支持状态查看、聊天、语音转写、语音合成和语音对话。
- 通过 Docker Compose 运行 Cloudflare Tunnel。

## 整体架构

```text
浏览器 / OpenAI 兼容客户端
        |
        | HTTP / SSE
        v
FastAPI Gateway
        |
        | JSON line TCP 协议
        v
unit-manager
        |
        | ZMQ RPC / PUB-SUB / PUSH-PULL
        v
StackFlow 业务节点
        |
        +-- rkllm_node  -> RKLLM runtime
        +-- asr_node    -> sherpa-onnx ASR
        +-- tts_node    -> 本地 TTS runtime
```

### 核心模块

| 模块 | 路径 | 作用 |
| --- | --- | --- |
| 混合通信层 | `hybrid-comm/` | 封装 ZMQ PUB/SUB、PUSH/PULL、RPC 等通信模式。 |
| Channel 与任务框架 | `infra-controller/` | 提供 `StackFlow` 基类、事件队列、work_id-channel 映射和节点生命周期接口。 |
| TCP 网络框架 | `network/` | Reactor 风格 TCP server、acceptor、connection、event loop 和线程池。 |
| 运行时管理器 | `unit-manager/` | 节点注册、work_id 分配、TCP/ZMQ 协议桥接和运行时元信息管理。 |
| AI 推理节点 | `node/llm`、`node/asr`、`node/tts` | 基于 StackFlow 接入 RKLLM、ASR、TTS 业务节点。 |
| API 网关 | `gateway/` | FastAPI 服务，对外提供 OpenAI 兼容 HTTP 接口。 |
| Web 控制台 | `web-vue/` | Vue 3 + Vite 前端，用于状态查看和推理工作流操作。 |
| 运行脚本 | `scripts/` | 启动、停止、状态检查、进程守护和冒烟测试。 |

## 设计要点

### ZMQ 混合通信组件

`hybrid-comm/include/pzmq.hpp` 将多种 ZMQ 通信模式封装到统一 C++ 接口中：

- `ZMQ_PUB` / `ZMQ_SUB`
- `ZMQ_PUSH` / `ZMQ_PULL`
- `ZMQ_RPC_FUN` / `ZMQ_RPC_CALL`

该封装负责 socket 创建、bind/connect 模式选择、后台接收线程、RPC 方法注册、
请求超时和自动重连配置，使业务层不需要直接处理 ZMQ 的细节。

### Channel 层

`infra-controller/include/channel.h` 提供 `llm_channel_obj`，用于管理单个任务的
通信 URL、请求 ID、work_id 和输出路径。业务节点可以通过 channel 将结果发布给
内部订阅者，也可以将结果推回外部客户端。

### StackFlow 任务框架

`infra-controller/include/StackFlow.h` 定义了业务节点的基类。它会注册
`setup`、`exit`、`pause`、`taskinfo` 等标准 RPC action，并通过 `eventpp`
把远程 RPC 请求转换成本地事件，再分发到虚函数接口。

业务节点只需要关注自身逻辑：

- `rkllm_node`：模型初始化、prompt 推理、流式 callback。
- `asr_node`：ASR stream 创建、PCM 分块输入、最终转写结果。
- `tts_node`：文本处理、语音合成、可选 WAV 音频返回。

### unit-manager

`unit-manager` 是运行时协调器，职责类似轻量级 rosmaster。它负责启动 ZMQ RPC
服务、管理节点元信息、分配通信 URL、接收外部 TCP 请求，并将 action 转发给
对应 unit。

默认运行时配置位于 `unit-manager/master_config.json`：

```json
{
  "config_tcp_server": 10001,
  "config_zmq_min_port": 5010,
  "config_zmq_max_port": 5555,
  "config_zmq_s_format": "ipc:///tmp/llm/%i.sock",
  "config_zmq_c_format": "ipc:///tmp/llm/%i.sock"
}
```

### OpenAI 兼容网关

FastAPI 网关位于 `gateway/app/main.py`，对外提供：

- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/audio/speech`
- `POST /v1/audio/transcriptions`
- `POST /v1/audio/conversations`

网关通过 TCP JSON-line 协议访问 `unit-manager`，并将底层错误转换为
OpenAI 风格的 HTTP 错误响应。

## 目录结构

```text
.
├── cloudflare/             # Cloudflare Worker 辅助文件
├── docker/                 # Docker 构建脚本和基础镜像配置
├── docs/                   # 部署说明和截图
├── gateway/                # FastAPI OpenAI 兼容网关
├── hybrid-comm/            # ZMQ 封装和轻量消息打包
├── infra-controller/       # StackFlow 任务框架和 channel 模块
├── network/                # Reactor 风格 TCP 网络库
├── node/
│   ├── asr/                # ASR 节点
│   ├── echo/               # 测试节点
│   ├── llm/                # RKLLM 节点
│   └── tts/                # TTS 节点
├── sample/                 # 测试客户端和压测脚本
├── scripts/                # 运行时守护和冒烟测试脚本
├── unit-manager/           # 运行时协调器和 TCP/ZMQ 桥接
├── web/                    # 旧版静态前端
└── web-vue/                # Vue 3 控制台
```

## 环境依赖

项目主要面向 Linux 边缘设备。`rkllm_node` 依赖 Rockchip RKLLM runtime 和模型
文件，因此完整推理流程需要在兼容 RKLLM runtime 的设备上运行。

通用依赖：

- CMake 3.12+
- C++17 编译器
- ZeroMQ 开发库
- eventpp
- simdjson
- glog
- Python 3
- Node.js 和 npm
- Docker 和 Docker Compose，仅在运行 Cloudflare Tunnel 或前端镜像时需要

模型、SDK 和第三方二进制依赖不提交到 git：

- `node/llm/model/`
- `node/llm/rknn-llm/`
- `node/asr/models/`
- `node/asr/third_party/`
- `node/tts/models/`
- `node/tts/third_party/`
- `node/tts/summer_tts/`

构建对应节点前，需要先准备好这些依赖文件。

## 构建

先构建并安装 StackFlow 静态库：

```bash
cmake -S infra-controller -B infra-controller/build
cmake --build infra-controller/build -j$(nproc)
cmake --install infra-controller/build
```

构建 `unit-manager`：

```bash
cmake -S unit-manager -B unit-manager/build
cmake --build unit-manager/build -j$(nproc)
```

构建 LLM 节点：

```bash
cmake -S node/llm -B node/llm/build
cmake --build node/llm/build -j$(nproc)
```

构建 TTS 节点：

```bash
cmake -S node/tts -B node/tts/build
cmake --build node/tts/build -j$(nproc)
```

构建 ASR 节点：

```bash
cmake -S node/asr -B node/asr/build
cmake --build node/asr/build -j$(nproc)
```

## Gateway 配置

安装 Python 依赖：

```bash
python3 -m pip install -r gateway/requirements.txt
```

单独启动 Gateway：

```bash
python3 -m uvicorn gateway.app.main:app --host 0.0.0.0 --port 8000
```

主要环境变量：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `UNIT_MANAGER_HOST` | `127.0.0.1` | unit-manager TCP 地址 |
| `UNIT_MANAGER_PORT` | `10001` | unit-manager TCP 端口 |
| `RKLLM_MODEL_ID` | `rkllm-local` | Gateway 暴露的 LLM 模型 ID |
| `TTS_MODEL_ID` | `tts-local` | Gateway 暴露的 TTS 模型 ID |
| `ASR_MODEL_ID` | `asr-local` | Gateway 暴露的 ASR 模型 ID |
| `RKLLM_TIMEOUT_SECONDS` | `300` | LLM 请求超时时间 |
| `TTS_TIMEOUT_SECONDS` | `180` | TTS 请求超时时间 |
| `ASR_TIMEOUT_SECONDS` | `60` | ASR 请求超时时间 |

## 启动运行时

推荐使用运行时守护脚本启动完整服务：

```bash
./scripts/start_runtime.sh
```

它会启动并守护：

- `unit-manager/build/unit_manager`
- `node/llm/build/rkllm_node`
- `node/tts/build/tts_node`
- `node/asr/build/asr_node`
- `python3 -m uvicorn gateway.app.main:app`

查看状态：

```bash
./scripts/status_runtime.sh
```

停止所有运行时进程：

```bash
./scripts/stop_runtime.sh
```

运行日志和 pid 文件会写入 `runtime/`。

### 运行时变量覆盖

```bash
RKLLM_MODEL_PATH=/models/qwen.rkllm \
TTS_MODEL_PATH=/models/tts.bin \
ASR_MODEL_DIR=/models/asr \
GATEWAY_PORT=8001 \
./scripts/start_runtime.sh
```

## 冒烟测试

运行时启动后执行：

```bash
./scripts/smoke_test_gateway.sh
```

该脚本会验证：

- `/health`
- `/v1/models`
- `/v1/chat/completions`
- `/v1/audio/speech`
- `/v1/audio/transcriptions`
- `/v1/audio/conversations`

可覆盖 Gateway 地址和 ASR 测试音频：

```bash
GATEWAY_BASE_URL=http://127.0.0.1:8000 \
ASR_TEST_WAV=node/asr/models/zipformer/test_wavs/3.wav \
./scripts/smoke_test_gateway.sh
```

## API 示例

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

查看模型：

```bash
curl http://127.0.0.1:8000/v1/models
```

非流式聊天：

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "rkllm-local",
    "messages": [{"role": "user", "content": "hello"}],
    "stream": false
  }'
```

流式聊天：

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "rkllm-local",
    "messages": [{"role": "user", "content": "介绍一下你自己"}],
    "stream": true
  }'
```

语音合成：

```bash
curl http://127.0.0.1:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{
    "model": "tts-local",
    "input": "你好，我是本地语音合成。",
    "voice": "0",
    "response_format": "wav",
    "speed": 1.0
  }' \
  --output out.wav
```

语音转写：

```bash
curl http://127.0.0.1:8000/v1/audio/transcriptions \
  -F model=asr-local \
  -F response_format=json \
  -F file=@node/asr/models/zipformer/test_wavs/3.wav
```

语音对话：

```bash
curl http://127.0.0.1:8000/v1/audio/conversations \
  -F file=@node/asr/models/zipformer/test_wavs/3.wav \
  -F model=rkllm-local \
  -F voice=0 \
  -F speed=1.0
```

## Web 控制台

先启动 Gateway，再运行前端：

```bash
cd web-vue
npm install
npm run dev
```

Vite dev server 监听 `0.0.0.0:8080`，默认将 `/health` 和 `/v1` 代理到
`http://127.0.0.1:8000`。

覆盖代理目标：

```bash
VITE_DEV_GATEWAY_TARGET=http://192.168.1.20:8000 npm run dev
```

构建生产版本：

```bash
cd web-vue
npm run build
```

构建并运行前端 Docker 镜像：

```bash
cd web-vue
docker build -t edge-ai-gateway-console .
docker run --rm -p 8080:80 edge-ai-gateway-console
```

## Cloudflare Tunnel

根目录 `docker-compose.yml` 会以常驻后台服务方式运行 `cloudflared`，使用 host
网络，并设置自动重启。

创建本地 `.env`：

```bash
cp .env.example .env
```

填写 tunnel token：

```bash
CLOUDFLARED_TOKEN=your_cloudflare_tunnel_token
```

启动 tunnel：

```bash
docker compose up -d
```

查看状态：

```bash
docker compose ps
```

查看日志：

```bash
docker compose logs -f cloudflared
```

停止 tunnel：

```bash
docker compose down
```

## 开发说明

- 根目录 `.env` 已被 git 忽略，因为其中可能包含 Cloudflare tunnel token。
- 生成的二进制、运行日志、模型权重、SDK 压缩包、WAV 文件和前端构建产物均不提交到 git。
- `sample/stress.py` 可用于对 `unit-manager` 发起 TCP 连接压测。
- 前端显示的 `Latency` 是浏览器访问 `/health` 的往返耗时，不是模型推理延迟。

## 常见问题

### `start_runtime.sh` 提示缺少二进制文件

需要先构建 `infra-controller`、`unit-manager` 和各个节点二进制。运行时守护脚本默认
从各模块的 `build/` 目录读取可执行文件。

### `rkllm_node` 无法启动

检查：

- `node/llm/rknn-llm/` 是否存在并包含 RKLLM runtime。
- `node/llm/model/Qwen3-1.7B.rkllm` 是否存在，或通过 `RKLLM_MODEL_PATH` 指定模型路径。
- 当前设备是否支持 RKLLM runtime。

### ASR 或 TTS 构建失败

ASR 和 TTS 节点依赖未纳入 git 的第三方模型和 runtime。请检查：

- `node/asr/third_party`
- `node/asr/models`
- `node/tts/third_party`
- `node/tts/models`
- `node/tts/summer_tts`

### Gateway 健康检查正常但推理失败

查看 `runtime/logs/` 下的日志：

- `unit-manager.log`
- `rkllm-node.log`
- `asr-node.log`
- `tts-node.log`
- `gateway.log`

同时确认 `UNIT_MANAGER_HOST` 和 `UNIT_MANAGER_PORT` 与实际运行的 `unit-manager`
一致。

## 相关文档

- `gateway/README.md`
- `web-vue/README.md`
- `scripts/README.md`
- `docs/deploy-vercel-cloudflare.md`
