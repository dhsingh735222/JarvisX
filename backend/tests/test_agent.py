import asyncio

import pytest

from app.agent import agent as agent_module
from app.agent import tools as tools_module
from app.agent.llm import LLMResponse, ToolCall
from app.models import Conversation


class FakeProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[list[dict]] = []

    async def chat(self, system, messages, tools):
        self.calls.append(messages)
        return self.responses.pop(0)


@pytest.fixture()
def conversation(db_session, test_user):
    convo = Conversation(user_id=test_user.id, title="Test")
    db_session.add(convo)
    db_session.commit()
    db_session.refresh(convo)
    return convo


def test_simple_reply_no_tools(db_session, test_user, conversation, monkeypatch):
    provider = FakeProvider([LLMResponse(text="Hello there!", tool_calls=[], stop_reason="end_turn")])
    monkeypatch.setattr(agent_module, "_provider_for_user", lambda db, user: provider)

    result = asyncio.run(agent_module.start_turn(db_session, test_user, conversation, "Hi"))

    assert result["pending_action"] is None
    assert result["new_messages"][-1].content == "Hello there!"
    assert len(provider.calls) == 1


def test_tool_call_then_approval_flow(db_session, test_user, conversation, monkeypatch, tmp_path):
    monkeypatch.setattr(tools_module.settings, "WORKSPACE_ROOT", str(tmp_path))
    (tmp_path / "old.txt").write_text("hello")

    responses = [
        LLMResponse(
            text="",
            tool_calls=[ToolCall(id="call_1", name="get_current_datetime", input={})],
            stop_reason="tool_use",
        ),
        LLMResponse(
            text="",
            tool_calls=[ToolCall(id="call_2", name="delete_path", input={"path": "old.txt"})],
            stop_reason="tool_use",
        ),
        LLMResponse(text="Done! I deleted old.txt.", tool_calls=[], stop_reason="end_turn"),
    ]
    provider = FakeProvider(responses)
    monkeypatch.setattr(agent_module, "_provider_for_user", lambda db, user: provider)

    result = asyncio.run(
        agent_module.start_turn(db_session, test_user, conversation, "What time is it, then delete old.txt")
    )

    # Second tool call (delete_path) requires approval -> loop pauses.
    assert result["pending_action"] is not None
    pending = result["pending_action"]
    assert pending.tool_name == "delete_path"
    assert pending.status == "pending"
    assert (tmp_path / "old.txt").exists()  # not deleted yet

    result2 = asyncio.run(agent_module.resume_turn(db_session, test_user, conversation, pending, approve=True))

    assert result2["pending_action"] is None
    assert not (tmp_path / "old.txt").exists()
    assert any("Done" in m.content for m in result2["new_messages"] if m.role == "assistant")
    # Three LLM calls total: initial, after datetime tool result, after delete tool result.
    assert len(provider.calls) == 3


def test_tool_call_denied(db_session, test_user, conversation, monkeypatch, tmp_path):
    monkeypatch.setattr(tools_module.settings, "WORKSPACE_ROOT", str(tmp_path))
    (tmp_path / "important.txt").write_text("keep me")

    responses = [
        LLMResponse(
            text="",
            tool_calls=[ToolCall(id="call_1", name="delete_path", input={"path": "important.txt"})],
            stop_reason="tool_use",
        ),
        LLMResponse(text="Okay, I left the file alone.", tool_calls=[], stop_reason="end_turn"),
    ]
    provider = FakeProvider(responses)
    monkeypatch.setattr(agent_module, "_provider_for_user", lambda db, user: provider)

    result = asyncio.run(agent_module.start_turn(db_session, test_user, conversation, "Delete important.txt"))
    pending = result["pending_action"]
    assert pending is not None

    result2 = asyncio.run(agent_module.resume_turn(db_session, test_user, conversation, pending, approve=False))

    assert result2["pending_action"] is None
    assert (tmp_path / "important.txt").exists()  # denied, file untouched
    assert "left the file alone" in result2["new_messages"][-1].content
