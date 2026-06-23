import json
import socket
import time
import uuid
from typing import Any, Dict, Iterable, Iterator, List, Optional


class UnitManagerError(RuntimeError):
    def __init__(self, message: str, code: int = -1):
        super().__init__(message)
        self.code = code
        self.message = message


def normalize_error(error: Any) -> Dict[str, Any]:
    if isinstance(error, str):
        try:
            return json.loads(error)
        except json.JSONDecodeError:
            return {"code": -1, "message": error}
    return error or {"code": 0, "message": ""}


class JsonLineClient:
    def __init__(self, host: str, port: int, connect_timeout: float = 10.0):
        self.sock = socket.create_connection((host, port), timeout=connect_timeout)
        self.buffer = b""

    def set_timeout(self, seconds: float) -> None:
        self.sock.settimeout(seconds)

    def send(self, message: Dict[str, Any]) -> None:
        payload = json.dumps(message, ensure_ascii=False) + "\n"
        self.sock.sendall(payload.encode("utf-8"))

    def receive(self) -> Dict[str, Any]:
        while b"\n" not in self.buffer:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise UnitManagerError("unit-manager closed the connection")
            self.buffer += chunk

        line, self.buffer = self.buffer.split(b"\n", 1)
        return json.loads(line.decode("utf-8"))

    def close(self) -> None:
        self.sock.close()


class UnitManagerClient:
    def __init__(self, host: str, port: int, timeout: float = 300.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.client: Optional[JsonLineClient] = None

    def __enter__(self) -> "UnitManagerClient":
        self.client = JsonLineClient(self.host, self.port)
        self.client.set_timeout(self.timeout)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.client is not None:
            self.client.close()

    def setup(self, unit_name: str) -> str:
        response = self._call(
            {
                "request_id": self._request_id(f"{unit_name}_setup"),
                "work_id": unit_name,
                "action": "setup",
                "object": f"{unit_name}.setup",
                "data": {},
            },
            f"{unit_name} setup",
        )
        work_id = response.get("work_id")
        if not isinstance(work_id, str) or not work_id:
            raise UnitManagerError(f"{unit_name} setup returned no work_id")
        return work_id

    def exit(self, work_id: str, unit_name: str) -> None:
        self._call(
            {
                "request_id": self._request_id(f"{unit_name}_exit"),
                "work_id": work_id,
                "action": "exit",
                "object": f"{unit_name}.exit",
                "data": {},
            },
            f"{unit_name} exit",
        )

    def rkllm_stream(self, work_id: str, prompt: str) -> Iterator[Dict[str, Any]]:
        if self.client is None:
            raise UnitManagerError("client is not connected")

        self.client.send(
            {
                "request_id": self._request_id("rkllm_infer"),
                "work_id": work_id,
                "action": "inference",
                "object": "rkllm.input",
                "data": {"prompt": prompt},
            }
        )

        while True:
            response = self.client.receive()
            self._ensure_success(response, "rkllm inference")
            if response.get("object") != "rkllm.result.stream":
                raise UnitManagerError(
                    f"unexpected rkllm response object: {response.get('object')}"
                )
            data = response.get("data") or {}
            yield data
            if data.get("finish", False):
                break

    def inference_once(
        self,
        work_id: str,
        object_name: str,
        data: Dict[str, Any],
        expected_object: str,
        action_name: str,
    ) -> Dict[str, Any]:
        if self.client is None:
            raise UnitManagerError("client is not connected")

        self.client.send(
            {
                "request_id": self._request_id(action_name),
                "work_id": work_id,
                "action": "inference",
                "object": object_name,
                "data": data,
            }
        )
        response = self.client.receive()
        self._ensure_success(response, action_name)
        if response.get("object") != expected_object:
            raise UnitManagerError(
                f"unexpected {action_name} response object: {response.get('object')}"
            )
        return response.get("data") or {}

    def asr_transcribe(
        self,
        work_id: str,
        chunks: Iterable[List[int]],
    ) -> str:
        final_text = ""
        for index, samples in enumerate(chunks):
            data = self._asr_inference(
                work_id,
                {
                    "samples": samples,
                    "finish": False,
                },
                f"asr_chunk_{index:06d}",
            )
            text = data.get("text", "")
            if isinstance(text, str) and text:
                final_text = text
            if data.get("final", False):
                return final_text.strip()

        data = self._asr_inference(
            work_id,
            {"finish": True},
            "asr_finish",
        )
        text = data.get("text", "")
        if isinstance(text, str) and text:
            final_text = text
        return final_text.strip()

    def _asr_inference(
        self,
        work_id: str,
        data: Dict[str, Any],
        request_prefix: str,
    ) -> Dict[str, Any]:
        response = self.inference_once(
            work_id,
            "asr.audio",
            data,
            "asr.result.stream",
            request_prefix,
        )
        return response

    def _call(self, message: Dict[str, Any], action: str) -> Dict[str, Any]:
        if self.client is None:
            raise UnitManagerError("client is not connected")
        self.client.send(message)
        response = self.client.receive()
        self._ensure_success(response, action)
        return response

    @staticmethod
    def _ensure_success(response: Dict[str, Any], action: str) -> None:
        error = normalize_error(response.get("error"))
        if error.get("code", 0) != 0:
            raise UnitManagerError(
                f"{action} failed: {error.get('message', error)}",
                int(error.get("code", -1)),
            )

    @staticmethod
    def _request_id(prefix: str) -> str:
        return f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
