import time
import uuid
from typing import Any, Dict, Iterable, List, Optional, Union


def build_prompt(messages: Iterable[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for message in messages:
        role = message.get("role", "user")
        content = normalize_content(message.get("content", ""))
        if not content:
            continue
        if role == "system":
            parts.append(f"System: {content}")
        elif role == "assistant":
            parts.append(f"Assistant: {content}")
        else:
            parts.append(f"User: {content}")
    parts.append("Assistant:")
    return "\n".join(parts)


def normalize_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(str(item.get("text", "")))
        return "\n".join(text for text in texts if text)
    return str(content)


def model_list(model_ids: Union[str, Iterable[str]]) -> Dict[str, Any]:
    now = int(time.time())
    if isinstance(model_ids, str):
        model_ids = [model_ids]

    return {
        "object": "list",
        "data": [
            {
                "id": model_id,
                "object": "model",
                "created": now,
                "owned_by": "edge-llm-infra",
            }
            for model_id in model_ids
        ],
    }


def chat_completion_response(
    model_id: str,
    content: str,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "id": request_id or f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model_id,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }


def chat_completion_chunk(
    model_id: str,
    delta: str,
    request_id: str,
    finish: bool = False,
    role: str = "",
) -> Dict[str, Any]:
    delta_body: Dict[str, Any] = {}
    if role:
        delta_body["role"] = role
    if delta:
        delta_body["content"] = delta

    return {
        "id": request_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model_id,
        "choices": [
            {
                "index": 0,
                "delta": {} if finish else delta_body,
                "finish_reason": "stop" if finish else None,
            }
        ],
    }
