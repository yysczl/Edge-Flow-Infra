import argparse
import json
import socket
import struct
import subprocess
import time
import wave


HOST = "127.0.0.1"
PORT = 10001
CHUNK_MILLISECONDS = 100


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


def ensure_success(response, action):
    error = response.get("error", {})
    if isinstance(error, str):
        error = json.loads(error)
    if error.get("code", 0) != 0:
        raise RuntimeError(f"{action} failed: {error}")


def read_wav_chunks(filename):
    with wave.open(filename, "rb") as wav:
        if wav.getnchannels() != 1:
            raise ValueError("WAV must be mono")
        if wav.getsampwidth() != 2:
            raise ValueError("WAV must use signed PCM16 samples")
        if wav.getframerate() != 16000:
            raise ValueError("WAV sample rate must be 16000 Hz")
        if wav.getcomptype() != "NONE":
            raise ValueError("WAV must be uncompressed PCM")

        frames_per_chunk = (
            wav.getframerate() * CHUNK_MILLISECONDS // 1000
        )

        while True:
            raw = wav.readframes(frames_per_chunk)
            if not raw:
                break
            count = len(raw) // 2
            yield list(struct.unpack(f"<{count}h", raw))


def microphone_chunks(device="plughw:1,0"):
    process = subprocess.Popen(
        [
            "arecord",
            "-D", device,
            "-f", "S16_LE",
            "-r", "16000",
            "-c", "1",
            "-t", "raw",
        ],
        stdout=subprocess.PIPE,
    )

    samples_per_chunk = 1600  # 100 ms
    bytes_per_chunk = samples_per_chunk * 2

    try:
        while True:
            raw = process.stdout.read(bytes_per_chunk)
            if len(raw) != bytes_per_chunk:
                if process.poll() not in (None, 0):
                    raise RuntimeError(
                        f"arecord exited with code {process.returncode}"
                    )
                break

            yield list(
                struct.unpack(f"<{samples_per_chunk}h", raw)
            )
    finally:
        if process.poll() is None:
            process.terminate()
        process.wait()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "wav",
        nargs="?",
        help="optional 16 kHz mono PCM16 WAV file",
    )
    parser.add_argument(
        "--device",
        default="plughw:1,0",
        help="ALSA capture device used when WAV is omitted",
    )
    args = parser.parse_args()

    client = JsonLineClient(HOST, PORT)
    work_id = None

    try:
        client.send(
            {
                "request_id": "asr_setup_001",
                "work_id": "asr",
                "action": "setup",
                "object": "asr.setup",
                "data": {},
            }
        )
        response = client.receive()
        ensure_success(response, "setup")
        work_id = response["work_id"]
        print("work_id:", work_id)

        time.sleep(0.2)
        client.sock.settimeout(30)

        last_text = ""
        if args.wav:
            chunks = read_wav_chunks(args.wav)
            print("input:", args.wav)
        else:
            chunks = microphone_chunks(args.device)
            print(
                f"microphone: {args.device}; press Ctrl+C to stop"
            )

        try:
            for index, samples in enumerate(chunks):
                client.send(
                    {
                        "request_id": f"asr_chunk_{index:06d}",
                        "work_id": work_id,
                        "action": "inference",
                        "object": "asr.audio",
                        "data": {
                            "samples": samples,
                            "finish": False,
                        },
                    }
                )

                response = client.receive()
                ensure_success(response, "inference")
                if response.get("object") != "asr.result.stream":
                    raise RuntimeError(
                        f"unexpected object: {response.get('object')}"
                    )

                result = response.get("data", {})
                text = result.get("text", "")
                if text != last_text:
                    print("partial:", text)
                    last_text = text

                if result.get("final", False):
                    print("final:", text)
                    last_text = ""
        except KeyboardInterrupt:
            print("\nstopping microphone...")
        finally:
            close_chunks = getattr(chunks, "close", None)
            if close_chunks is not None:
                close_chunks()

        client.send(
            {
                "request_id": "asr_finish_001",
                "work_id": work_id,
                "action": "inference",
                "object": "asr.audio",
                "data": {"finish": True},
            }
        )
        response = client.receive()
        ensure_success(response, "finish")
        print("final:", response.get("data", {}).get("text", ""))
    finally:
        if work_id is not None:
            client.sock.settimeout(10)
            client.send(
                {
                    "request_id": "asr_exit_001",
                    "work_id": work_id,
                    "action": "exit",
                    "object": "asr.exit",
                    "data": {},
                }
            )
            response = client.receive()
            ensure_success(response, "exit")

        client.close()


if __name__ == "__main__":
    main()
