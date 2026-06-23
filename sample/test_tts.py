import argparse
import json
import socket
import time

# python3 sample/test_tts.py "你好，我是 TTS 节点测试。"

HOST = "127.0.0.1"
PORT = 10001
INFERENCE_TIMEOUT_SECONDS = 120


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


def main():
    parser = argparse.ArgumentParser(description="Test the tts node through unit-manager.")
    parser.add_argument(
        "text",
        nargs="?",
        default="你好，我是 TTS 节点测试。",
        help="text to synthesize and play",
    )
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--speaker-id", type=int, default=0)
    parser.add_argument(
        "--length-scale",
        type=float,
        default=1.0,
        help="SummerTTS length scale; larger usually speaks slower",
    )
    args = parser.parse_args()

    client = JsonLineClient(args.host, args.port)
    work_id = None

    try:
        client.send(
            {
                "request_id": "tts_setup_001",
                "work_id": "tts",
                "action": "setup",
                "object": "tts.setup",
                "data": {},
            }
        )
        setup_response = client.receive()
        print("setup:", json.dumps(setup_response, ensure_ascii=False, indent=2))
        ensure_success(setup_response, "setup")

        work_id = setup_response["work_id"]

        # Give the ZMQ subscriber time to finish connecting before first input.
        time.sleep(0.2)

        client.sock.settimeout(INFERENCE_TIMEOUT_SECONDS)
        client.send(
            {
                "request_id": "tts_infer_001",
                "work_id": work_id,
                "action": "inference",
                "object": "tts.input",
                "data": {
                    "text": args.text,
                    "speaker_id": args.speaker_id,
                    "length_scale": args.length_scale,
                },
            }
        )

        inference_response = client.receive()
        print(
            "inference:",
            json.dumps(inference_response, ensure_ascii=False, indent=2),
        )
        ensure_success(inference_response, "inference")

        if inference_response.get("object") != "tts.play.done":
            raise RuntimeError(
                f"unexpected response object: {inference_response.get('object')}"
            )

    finally:
        if work_id is not None:
            client.sock.settimeout(10)
            client.send(
                {
                    "request_id": "tts_exit_001",
                    "work_id": work_id,
                    "action": "exit",
                    "object": "tts.exit",
                    "data": {},
                }
            )
            exit_response = client.receive()
            print("exit:", json.dumps(exit_response, ensure_ascii=False, indent=2))

        client.close()


if __name__ == "__main__":
    main()
