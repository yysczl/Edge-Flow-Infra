export async function streamChatCompletion(url, payload, onDelta) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok || !response.body) {
    const errorPayload = await safeJson(response);
    throw new Error(errorPayload?.error?.message || `HTTP ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let content = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      buffer += decoder.decode();
      content = processBuffer(buffer, content, onDelta, true).content;
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const result = processBuffer(buffer, content, onDelta, false);
    buffer = result.buffer;
    content = result.content;
  }

  return content;
}

function processBuffer(buffer, content, onDelta, flush) {
  const normalized = buffer.replace(/\r\n/g, "\n");
  const events = normalized.split("\n\n");
  const remainder = flush ? "" : events.pop() || "";

  for (const event of events) {
    const data = parseSseData(event);
    if (!data || data === "[DONE]") {
      continue;
    }

    let payloadChunk;
    try {
      payloadChunk = JSON.parse(data);
    } catch (error) {
      throw new Error(`Invalid SSE JSON chunk: ${error.message}`);
    }

    if (payloadChunk.error?.message) {
      throw new Error(payloadChunk.error.message);
    }

    const delta = payloadChunk.choices?.[0]?.delta?.content || "";
    if (delta) {
      content += delta;
      onDelta?.(delta, content);
    }
  }

  return {
    buffer: remainder,
    content,
  };
}

function parseSseData(event) {
  return event
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trim())
    .join("\n")
    .trim();
}

async function safeJson(response) {
  try {
    return await response.json();
  } catch (_) {
    return null;
  }
}
