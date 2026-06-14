"""LLM provider abstraction.

A canonical message format is used internally:

    {"role": "user" | "assistant" | "tool",
     "content": str,
     "tool_calls": [{"id": str, "name": str, "input": dict}] | None,
     "tool_use_id": str | None,
     "tool_name": str | None}

Each provider converts to/from its own wire format. `tools` is a list of
canonical tool definitions: {"name", "description", "parameters"}.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"  # "end_turn" | "tool_use"


class LLMError(Exception):
    pass


class BaseLLMProvider:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def chat(self, system: str, messages: list[dict], tools: list[dict]) -> LLMResponse:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Anthropic (Claude)
# ---------------------------------------------------------------------------

class AnthropicProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5"):
        super().__init__(api_key, model)
        if not api_key:
            raise LLMError("No Anthropic API key configured. Add one in Settings.")
        import anthropic

        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def chat(self, system: str, messages: list[dict], tools: list[dict]) -> LLMResponse:
        anthropic_messages = []
        for m in messages:
            if m["role"] == "tool":
                anthropic_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": m["tool_use_id"],
                                "content": m["content"],
                            }
                        ],
                    }
                )
            elif m["role"] == "assistant" and m.get("tool_calls"):
                blocks: list[dict] = []
                if m.get("content"):
                    blocks.append({"type": "text", "text": m["content"]})
                for tc in m["tool_calls"]:
                    blocks.append({"type": "tool_use", "id": tc["id"], "name": tc["name"], "input": tc["input"]})
                anthropic_messages.append({"role": "assistant", "content": blocks})
            else:
                anthropic_messages.append({"role": m["role"], "content": m["content"]})

        anthropic_tools = [
            {"name": t["name"], "description": t["description"], "input_schema": t["parameters"]} for t in tools
        ]

        response = await self._client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=anthropic_messages,
            tools=anthropic_tools or None,
        )

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, input=block.input))

        return LLMResponse(text="".join(text_parts), tool_calls=tool_calls, stop_reason=response.stop_reason)


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------

class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        super().__init__(api_key, model)
        if not api_key:
            raise LLMError("No OpenAI API key configured. Add one in Settings.")
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key)

    async def chat(self, system: str, messages: list[dict], tools: list[dict]) -> LLMResponse:
        openai_messages: list[dict] = [{"role": "system", "content": system}]
        for m in messages:
            if m["role"] == "tool":
                openai_messages.append(
                    {"role": "tool", "tool_call_id": m["tool_use_id"], "content": m["content"]}
                )
            elif m["role"] == "assistant" and m.get("tool_calls"):
                openai_messages.append(
                    {
                        "role": "assistant",
                        "content": m.get("content") or None,
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {"name": tc["name"], "arguments": json.dumps(tc["input"])},
                            }
                            for tc in m["tool_calls"]
                        ],
                    }
                )
            else:
                openai_messages.append({"role": m["role"], "content": m["content"]})

        openai_tools = [
            {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}}
            for t in tools
        ]

        response = await self._client.chat.completions.create(
            model=self.model,
            messages=openai_messages,
            tools=openai_tools or None,
        )

        choice = response.choices[0]
        message = choice.message
        tool_calls: list[ToolCall] = []
        for tc in message.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, input=args))

        stop_reason = "tool_use" if tool_calls else "end_turn"
        return LLMResponse(text=message.content or "", tool_calls=tool_calls, stop_reason=stop_reason)


# ---------------------------------------------------------------------------
# Google Gemini
# ---------------------------------------------------------------------------

class GoogleProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        super().__init__(api_key, model)
        if not api_key:
            raise LLMError("No Google API key configured. Add one in Settings.")
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        self._genai = genai

    async def chat(self, system: str, messages: list[dict], tools: list[dict]) -> LLMResponse:
        gemini_tools = None
        if tools:
            gemini_tools = [
                {
                    "function_declarations": [
                        {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}
                        for t in tools
                    ]
                }
            ]

        model = self._genai.GenerativeModel(model_name=self.model, system_instruction=system, tools=gemini_tools)

        history = []
        for m in messages:
            if m["role"] == "user":
                history.append({"role": "user", "parts": [{"text": m["content"]}]})
            elif m["role"] == "assistant":
                parts: list[dict] = []
                if m.get("content"):
                    parts.append({"text": m["content"]})
                for tc in m.get("tool_calls") or []:
                    parts.append({"function_call": {"name": tc["name"], "args": tc["input"]}})
                history.append({"role": "model", "parts": parts})
            elif m["role"] == "tool":
                history.append(
                    {
                        "role": "user",
                        "parts": [
                            {
                                "function_response": {
                                    "name": m.get("tool_name", ""),
                                    "response": {"result": m["content"]},
                                }
                            }
                        ],
                    }
                )

        if not history:
            history = [{"role": "user", "parts": [{"text": ""}]}]

        last = history[-1]
        convo_history = history[:-1]

        chat = model.start_chat(history=convo_history)
        response = await chat.send_message_async(last["parts"])

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for part in response.candidates[0].content.parts:
            if getattr(part, "text", None):
                text_parts.append(part.text)
            fc = getattr(part, "function_call", None)
            if fc:
                tool_calls.append(ToolCall(id=f"call_{fc.name}_{len(tool_calls)}", name=fc.name, input=dict(fc.args)))

        stop_reason = "tool_use" if tool_calls else "end_turn"
        return LLMResponse(text="".join(text_parts), tool_calls=tool_calls, stop_reason=stop_reason)


# ---------------------------------------------------------------------------
# Ollama (local models)
# ---------------------------------------------------------------------------

def _recover_text_tool_call(content: str, tool_names: set[str]) -> ToolCall | None:
    """Small local models sometimes emit a tool call as raw (and often
    slightly malformed) JSON in the message content instead of using
    Ollama's structured `tool_calls` field, e.g.

        {"name":"web_search","parameters {"query":"java"}}

    Try to recover the tool name and arguments from text like that.
    """
    content = content.strip()
    if not content.startswith("{") or '"name"' not in content:
        return None

    name_match = re.search(r'"name"\s*:\s*"([^"]+)"', content)
    if not name_match or name_match.group(1) not in tool_names:
        return None

    args: dict = {}
    params_match = re.search(r'"(?:parameters|arguments|input)"?\s*:?\s*(\{.*)', content, re.DOTALL)
    if params_match:
        remainder = params_match.group(1)
        depth = 0
        end = None
        for i, ch in enumerate(remainder):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end:
            try:
                args = json.loads(remainder[:end])
            except json.JSONDecodeError:
                args = {}

    return ToolCall(id="call_0", name=name_match.group(1), input=args)


class OllamaProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str, base_url: str):
        super().__init__(api_key, model)
        self.base_url = base_url.rstrip("/")

    async def chat(self, system: str, messages: list[dict], tools: list[dict]) -> LLMResponse:
        import httpx

        ollama_messages: list[dict] = [{"role": "system", "content": system}]
        for m in messages:
            if m["role"] == "tool":
                ollama_messages.append({"role": "tool", "content": m["content"]})
            elif m["role"] == "assistant" and m.get("tool_calls"):
                ollama_messages.append(
                    {
                        "role": "assistant",
                        "content": m.get("content") or "",
                        "tool_calls": [
                            {"function": {"name": tc["name"], "arguments": tc["input"]}} for tc in m["tool_calls"]
                        ],
                    }
                )
            else:
                ollama_messages.append({"role": m["role"], "content": m["content"]})

        ollama_tools = [
            {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}}
            for t in tools
        ]

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/api/chat",
                json={"model": self.model, "messages": ollama_messages, "tools": ollama_tools or None, "stream": False},
            )
            resp.raise_for_status()
            data = resp.json()

        message = data.get("message", {})
        tool_calls: list[ToolCall] = []
        for i, tc in enumerate(message.get("tool_calls") or []):
            fn = tc.get("function", {})
            tool_calls.append(ToolCall(id=f"call_{i}", name=fn.get("name", ""), input=fn.get("arguments", {}) or {}))

        text = message.get("content", "")
        if not tool_calls:
            recovered = _recover_text_tool_call(text, {t["name"] for t in tools})
            if recovered:
                tool_calls.append(recovered)
                text = ""

        stop_reason = "tool_use" if tool_calls else "end_turn"
        return LLMResponse(text=text, tool_calls=tool_calls, stop_reason=stop_reason)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_provider(provider: str, model: str, api_key: str, ollama_base_url: str = "http://localhost:11434") -> BaseLLMProvider:
    provider = provider.lower()
    if provider == "anthropic":
        return AnthropicProvider(api_key=api_key, model=model)
    if provider == "openai":
        return OpenAIProvider(api_key=api_key, model=model)
    if provider == "google":
        return GoogleProvider(api_key=api_key, model=model)
    if provider == "ollama":
        return OllamaProvider(api_key=api_key, model=model, base_url=ollama_base_url)
    raise LLMError(f"Unknown LLM provider: {provider}")


DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-5",
    "openai": "gpt-4o",
    "google": "gemini-2.0-flash",
    "ollama": "llama3.1",
}
