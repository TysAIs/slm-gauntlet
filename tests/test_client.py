"""Tests for the OpenAI-compatible client (mocked transport)."""

import json

import httpx
import pytest

from gauntlet.client import ClientError, GauntletClient


def _resp(payload, status=200):
    return httpx.Response(status, json=payload, request=httpx.Request("POST", "http://test/v1/chat/completions"))


def _transport(handler):
    return httpx.MockTransport(handler)


COMPLETION = {
    "id": "c1",
    "choices": [{"message": {"role": "assistant", "content": "hello"}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
}

TOOL_CALL = {
    "id": "c2",
    "choices": [{
        "message": {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "t1",
                "type": "function",
                "function": {"name": "get_weather", "arguments": '{"city": "Paris"}'},
            }],
        },
        "finish_reason": "tool_calls",
    }],
    "usage": {"prompt_tokens": 20, "completion_tokens": 8},
}


async def test_basic_completion():
    def handler(request):
        body = json.loads(request.content)
        assert body["model"] == "test-model"
        return _resp(COMPLETION)

    client = GauntletClient("http://test/v1", "test-model", transport=_transport(handler))
    out = await client.chat([{"role": "user", "content": "hi"}])
    assert out.content == "hello"
    assert out.usage.prompt_tokens == 10
    assert out.usage.completion_tokens == 5


async def test_tool_call_roundtrip():
    seen = {}

    def handler(request):
        body = json.loads(request.content)
        if "tools" in body:
            seen["tools"] = body["tools"]
            return _resp(TOOL_CALL)
        return _resp(COMPLETION)

    client = GauntletClient("http://test/v1", "test-model", transport=_transport(handler))
    tools = [{"type": "function", "function": {"name": "get_weather", "parameters": {}}}]
    out = await client.chat([{"role": "user", "content": "weather?"}], tools=tools)
    assert out.tool_calls[0].name == "get_weather"
    assert out.tool_calls[0].arguments == {"city": "Paris"}
    assert seen["tools"] == tools


async def test_500_retries_then_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(500, request=request)
        return _resp(COMPLETION)

    client = GauntletClient("http://test/v1", "test-model", transport=_transport(handler), max_retries=3)
    out = await client.chat([{"role": "user", "content": "hi"}])
    assert out.content == "hello"
    assert calls["n"] == 3


async def test_500_exhausts_retries():
    def handler(request):
        return httpx.Response(500, request=request)

    client = GauntletClient("http://test/v1", "test-model", transport=_transport(handler), max_retries=2)
    with pytest.raises(ClientError):
        await client.chat([{"role": "user", "content": "hi"}])


async def test_usage_extraction_missing_is_zero():
    payload = {"id": "c3", "choices": [{"message": {"content": "x"}, "finish_reason": "stop"}]}
    client = GauntletClient("http://test/v1", "test-model", transport=_transport(lambda r: _resp(payload)))
    out = await client.chat([{"role": "user", "content": "hi"}])
    assert out.usage.prompt_tokens == 0
    assert out.usage.completion_tokens == 0
