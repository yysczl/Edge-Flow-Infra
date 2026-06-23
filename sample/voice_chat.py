'''
同步版语聊闭环：

```text
setup asr/rkllm/tts
-> 麦克风录音
-> asr final 文本
-> rkllm 流式回答并拼接完整文本
-> tts 播放回答
-> 下一轮
```

运行示例：

```bash
python3 sample/voice_chat.py --device plughw:1,0 --speaker-id 0 --length-scale 1.0
```

限制轮数测试：

```bash
python3 sample/voice_chat.py --device plughw:1,0 --max-turns 1
```

可改 system prompt：

```bash
python3 sample/voice_chat.py \
  --device plughw:1,0 \
  --system-prompt "你是一个简洁的语音助手，请每次回答不超过三句话。"
```

退出用 `Ctrl+C`，脚本会按顺序释放 `tts`、`rkllm`、`asr` task。

我没有实际连接 node 测试，只做了语法检查：

```bash
python3 -m py_compile sample/voice_chat.py
```
'''
import argparse
import json
import socket
import struct
import subprocess
import time


HOST = "127.0.0.1"
PORT = 10001
CHUNK_MILLISECONDS = 100
ASR_TIMEOUT_SECONDS = 30
LLM_TIMEOUT_SECONDS = 300
TTS_TIMEOUT_SECONDS = 180


class JsonLineClient:
    def __init__(self, host, port):
        self.sock = socket.create_connection((host, port), timeout=10)
        self.buffer = b""

    def send(self, message):
        payload = json.dumps(message, ensure_ascii=False) + "\n"
        self.sock.sendall(payload.encode("utf-8"))

    def receive(self):
        while b"\n" not in self.buffer:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("unit-manager closed the connection")
            self.buffer += chunk

        line, self.buffer = self.buffer.split(b"\n", 1)
        return json.loads(line.decode("utf-8"))

    def close(self):
        self.sock.close()


def normalize_error(error):
    if isinstance(error, str):
        try:
            return json.loads(error)
        except json.JSONDecodeError:
            return {"code": -1, "message": error}
    return error or {}


def ensure_success(response, action):
    error = normalize_error(response.get("error", {}))
    if error.get("code", 0) != 0:
        raise RuntimeError(f"{action} failed: {error}")


def setup_node(client, unit_name):
    request_id = f"{unit_name}_setup_001"
    client.send(
        {
            "request_id": request_id,
            "work_id": unit_name,
            "action": "setup",
            "object": f"{unit_name}.setup",
            "data": {},
        }
    )
    response = client.receive()
    print(f"{unit_name} setup:", json.dumps(response, ensure_ascii=False, indent=2))
    ensure_success(response, f"{unit_name} setup")
    return response["work_id"]


def exit_node(client, work_id, unit_name):
    client.send(
        {
            "request_id": f"{unit_name}_exit_001",
            "work_id": work_id,
            "action": "exit",
            "object": f"{unit_name}.exit",
            "data": {},
        }
    )
    response = client.receive()
    print(f"{unit_name} exit:", json.dumps(response, ensure_ascii=False, indent=2))
    ensure_success(response, f"{unit_name} exit")


def microphone_chunks(device, chunk_milliseconds):
    process = subprocess.Popen(
        [
            "arecord",
            "-D",
            device,
            "-f",
            "S16_LE",
            "-r",
            "16000",
            "-c",
            "1",
            "-t",
            "raw",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    samples_per_chunk = 16000 * chunk_milliseconds // 1000
    bytes_per_chunk = samples_per_chunk * 2

    try:
        while True:
            raw = process.stdout.read(bytes_per_chunk)
            if len(raw) != bytes_per_chunk:
                if process.poll() not in (None, 0):
                    raise RuntimeError(f"arecord exited with code {process.returncode}")
                break
            yield list(struct.unpack(f"<{samples_per_chunk}h", raw))
    finally:
        if process.poll() is None:
            process.terminate()
        process.wait()


def listen_once(client, asr_work_id, device, chunk_milliseconds):
    print("\nlistening...")
    client.sock.settimeout(ASR_TIMEOUT_SECONDS)
    last_partial = ""

    for index, samples in enumerate(microphone_chunks(device, chunk_milliseconds)):
        client.send(
            {
                "request_id": f"voice_asr_chunk_{index:06d}",
                "work_id": asr_work_id,
                "action": "inference",
                "object": "asr.audio",
                "data": {
                    "samples": samples,
                    "finish": False,
                },
            }
        )

        response = client.receive()
        ensure_success(response, "asr inference")
        if response.get("object") != "asr.result.stream":
            raise RuntimeError(f"unexpected ASR object: {response.get('object')}")

        data = response.get("data", {})
        text = data.get("text", "")
        if text and text != last_partial:
            print("asr partial:", text)
            last_partial = text

        if data.get("final", False):
            final_text = text.strip()
            print("asr final:", final_text)
            return final_text

    return ""


def ask_llm(client, llm_work_id, prompt):
    client.sock.settimeout(LLM_TIMEOUT_SECONDS)
    client.send(
        {
            "request_id": "voice_llm_infer_001",
            "work_id": llm_work_id,
            "action": "inference",
            "object": "rkllm.input",
            "data": {
                "prompt": prompt,
            },
        }
    )

    print("assistant:", end="", flush=True)
    full_text = ""
    while True:
        response = client.receive()
        ensure_success(response, "llm inference")

        if response.get("object") != "rkllm.result.stream":
            raise RuntimeError(f"unexpected LLM object: {response.get('object')}")

        data = response.get("data", {})
        delta = data.get("delta", "")
        finish = data.get("finish", False)

        if delta:
            print(delta, end="", flush=True)
            full_text += delta

        if finish:
            print()
            return full_text.strip()


def play_tts(client, tts_work_id, text, speaker_id, length_scale):
    client.sock.settimeout(TTS_TIMEOUT_SECONDS)
    client.send(
        {
            "request_id": "voice_tts_infer_001",
            "work_id": tts_work_id,
            "action": "inference",
            "object": "tts.input",
            "data": {
                "text": text,
                "speaker_id": speaker_id,
                "length_scale": length_scale,
            },
        }
    )

    response = client.receive()
    ensure_success(response, "tts inference")
    if response.get("object") != "tts.play.done":
        raise RuntimeError(f"unexpected TTS object: {response.get('object')}")

    data = response.get("data", {})
    print(
        "tts done:",
        f"samples={data.get('samples')}",
        f"sample_rate={data.get('sample_rate')}",
    )


def build_prompt(user_text, system_prompt):
    if not system_prompt:
        return user_text
    return f"{system_prompt}\n\n用户：{user_text}\n助手："


def main():
    parser = argparse.ArgumentParser(
        description="Run a simple ASR -> LLM -> TTS voice chat loop."
    )
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument(
        "--device",
        default="plughw:1,0",
        help="ALSA capture device for arecord",
    )
    parser.add_argument(
        "--chunk-ms",
        type=int,
        default=CHUNK_MILLISECONDS,
        help="microphone chunk size in milliseconds",
    )
    parser.add_argument("--speaker-id", type=int, default=0)
    parser.add_argument("--length-scale", type=float, default=1.0)
    parser.add_argument(
        "--max-turns",
        type=int,
        default=0,
        help="0 means unlimited",
    )
    parser.add_argument(
        "--system-prompt",
        default="你是一个语音聊天助手，请用简洁自然的中文回答。",
    )
    args = parser.parse_args()

    client = JsonLineClient(args.host, args.port)
    work_ids = {}

    try:
        work_ids["asr"] = setup_node(client, "asr")
        work_ids["rkllm"] = setup_node(client, "rkllm")
        work_ids["tts"] = setup_node(client, "tts")

        # Give subscribers time to connect before first inference.
        time.sleep(0.3)

        turn = 0
        print("\nvoice chat started. Press Ctrl+C to stop.")
        while args.max_turns <= 0 or turn < args.max_turns:
            turn += 1
            user_text = listen_once(
                client,
                work_ids["asr"],
                args.device,
                args.chunk_ms,
            )
            if not user_text:
                print("empty ASR result, listening again.")
                continue

            print("user:", user_text)
            answer = ask_llm(
                client,
                work_ids["rkllm"],
                build_prompt(user_text, args.system_prompt),
            )
            if not answer:
                print("empty LLM result, listening again.")
                continue

            play_tts(
                client,
                work_ids["tts"],
                answer,
                args.speaker_id,
                args.length_scale,
            )

    except KeyboardInterrupt:
        print("\nstopping voice chat...")
    finally:
        client.sock.settimeout(10)
        for unit_name in ("tts", "rkllm", "asr"):
            work_id = work_ids.get(unit_name)
            if work_id is None:
                continue
            try:
                exit_node(client, work_id, unit_name)
            except Exception as exc:
                print(f"{unit_name} exit failed: {exc}")
        client.close()


if __name__ == "__main__":
    main()
