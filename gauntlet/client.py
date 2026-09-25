"""OpenAI-compatible chat-completions client.

Minimal dependency surface: httpx only, no SDK. Handles chat, tool calls,
usage extraction, and retry-on-5xx with exponential backoff.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

import httpx


class ClientError(RuntimeError):
    """Raised when the endpoint fails after retries or returns malformed output."""


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict  # parsed JSON args


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class ChatResult:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None
    usage: Usage = field(default_factory=Usage)
    ttft: float | None = None  # seconds to first token (streaming only)


class GauntletClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 600.0,
        max_retries: int = 3,
        api_key: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_retries = max_retries
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._http = httpx.AsyncClient(
            base_url=base_url, timeout=timeout, transport=transport, headers=headers
        )

    async def close(self):
        await self._http.aclose()

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        extra: dict | None = None,
        no_think: bool = False,
    ) -> ChatResult:
        body: dict = {"model": self.model, "messages": messages, "temperature": temperature}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if max_tokens:
            body["max_tokens"] = max_tokens
        if no_think:
            # llama.cpp per-request think-mode disable (works for templates
            # exposing enable_thinking; ignored gracefully by others)
            body.setdefault("chat_template_kwargs", {})["enable_thinking"] = False
        if extra:
            body.update(extra)

        resp = await self._post_with_retry(body)
        data = resp.json()
        try:
            choice = data["choices"][0]
            msg = choice["message"]
        except (KeyError, IndexError) as e:
            raise ClientError(f"malformed completion response: {e}: {data!r}") from e

        tool_calls = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function", {})
            args = fn.get("arguments", "{}")
            if isinstance(args, str):
                try:
                    args = __import__("json").loads(args)
                except ValueError:
                    args = {"_raw": args}
            tool_calls.append(ToolCall(id=tc.get("id", ""), name=fn.get("name", ""), arguments=args))

        usage_raw = data.get("usage") or {}
        return ChatResult(
            content=msg.get("content"),
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason"),
            usage=Usage(
                prompt_tokens=usage_raw.get("prompt_tokens", 0),
                completion_tokens=usage_raw.get("completion_tokens", 0),
            ),
        )

    async def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.0,
        max_tokens: int | None = None,
        no_think: bool = True,
    ) -> ChatResult:
        """Streaming completion; records TTFT and concatenates content."""
        body: dict = {"model": self.model, "messages": messages, "temperature": temperature, "stream": True}
        if max_tokens:
            body["max_tokens"] = max_tokens
        if no_think:
            body.setdefault("chat_template_kwargs", {})["enable_thinking"] = False

        start = time.perf_counter()
        resp = await self._post_with_retry(body, stream=True)
        parts: list[str] = []
        completion_tokens = 0
        ttft = None
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload.strip() == "[DONE]":
                break
            chunk = __import__("json").loads(payload)
            delta = (chunk.get("choices") or [{}])[0].get("delta", {})
            content = delta.get("content")
            if content:
                if ttft is None:
                    ttft = time.perf_counter() - start
                parts.append(content)
            if chunk.get("usage"):
                completion_tokens = chunk["usage"].get("completion_tokens", completion_tokens)

        if ttft is None:
            ttft = time.perf_counter() - start
        return ChatResult(
            content="".join(parts),
            usage=Usage(completion_tokens=completion_tokens),
            ttft=ttft,
        )

    async def _post_with_retry(self, body: dict, stream: bool = False) -> httpx.Response:
        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = await self._http.post("/chat/completions", json=body)
                if resp.status_code >= 500:
                    last_err = ClientError(f"server error {resp.status_code}")
                elif resp.status_code >= 400:
                    raise ClientError(f"client error {resp.status_code}: {resp.text[:300]}")
                else:
                    if stream:
                        resp.read()  # materialize for aiter_lines with mock transport
                    return resp
            except httpx.TransportError as e:
                last_err = e
            if attempt < self.max_retries:
                await asyncio.sleep(0.05 * (2**attempt))
        raise ClientError(f"endpoint failed after {self.max_retries + 1} attempts: {last_err}")
