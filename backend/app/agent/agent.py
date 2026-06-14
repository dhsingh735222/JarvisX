"""Core agent loop: takes a user message, talks to the configured LLM with
tool-use enabled, executes tools (pausing for approval when required), and
persists everything to the conversation history + activity log.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from app.agent.llm import DEFAULT_MODELS, LLMError, get_provider
from app.agent.tools import TOOLS, ToolContext, ToolError, execute_tool, get_tool
from app.config import get_settings
from app.models import ActivityLog, ApiKey, Conversation, Message, PendingAction, User
from app.security import decrypt_value

logger = logging.getLogger("jarvisx.agent")
settings = get_settings()

MAX_ITERATIONS = 8

SYSTEM_PROMPT = """You are JarvisX, a proactive personal AI assistant running locally on the user's computer.

You can converse naturally and you can take real actions on the user's machine using the tools available
to you (file management, opening apps/URLs, web search, and long-term memory).

Guidelines:
- Be concise, warm, and direct - like a capable assistant, not a chatbot.
- When the user asks you to do something on their computer, use the appropriate tool rather than just
  describing how to do it.
- Some tools (rename_path, move_path, delete_path, overwriting files) require explicit user approval.
  Call them anyway when appropriate - the system will pause and ask the user to approve or deny.
- Use `remember` to save durable facts/preferences about the user, and `recall` to retrieve them.
- All file operations are sandboxed to the user's workspace directory; you cannot access paths outside it.
- If a tool call fails, explain the error to the user in plain language and suggest next steps.
- Always confirm what action you took (or what you found) in your final reply.
"""

CANONICAL_TOOLS = [{"name": t.name, "description": t.description, "parameters": t.parameters} for t in TOOLS]


def _get_api_key(db: Session, user_id: int, provider: str) -> str:
    row = db.query(ApiKey).filter(ApiKey.user_id == user_id, ApiKey.provider == provider).first()
    if row:
        return decrypt_value(row.encrypted_value)
    env_map = {
        "anthropic": settings.ANTHROPIC_API_KEY,
        "openai": settings.OPENAI_API_KEY,
        "google": settings.GOOGLE_API_KEY,
    }
    return env_map.get(provider, "")


def _provider_for_user(db: Session, user: User):
    provider_name = user.llm_provider or settings.DEFAULT_LLM_PROVIDER
    model = user.llm_model or DEFAULT_MODELS.get(provider_name, settings.DEFAULT_LLM_MODEL)
    api_key = _get_api_key(db, user.id, provider_name)
    if provider_name != "ollama" and not api_key:
        raise LLMError(
            f"No API key configured for '{provider_name}'. Add one in Settings, "
            "or switch the LLM provider to 'ollama' to use a local model."
        )
    return get_provider(provider_name, model, api_key, settings.OLLAMA_BASE_URL)


def _message_to_canonical(m: Message) -> dict:
    return {
        "role": m.role,
        "content": m.content or "",
        "tool_calls": m.tool_calls,
        "tool_use_id": m.tool_use_id,
        "tool_name": m.tool_name,
    }


def _load_canonical_messages(conversation: Conversation) -> list[dict]:
    return [_message_to_canonical(m) for m in conversation.messages]


def _log_activity(
    db: Session,
    user_id: int,
    action_type: str,
    status: str,
    tool_name: str | None = None,
    input_data: dict | None = None,
    output_data: dict | str | None = None,
) -> None:
    if isinstance(output_data, str):
        output_data = {"message": output_data}
    db.add(
        ActivityLog(
            user_id=user_id,
            action_type=action_type,
            tool_name=tool_name,
            input_data=input_data,
            output_data=output_data,
            status=status,
        )
    )
    db.commit()


async def start_turn(db: Session, user: User, conversation: Conversation, user_message: str) -> dict:
    """Persist the user's message and run the agent loop until it produces a
    final reply or pauses for approval."""
    db.add(Message(conversation_id=conversation.id, role="user", content=user_message))
    db.commit()
    db.refresh(conversation)

    try:
        provider = _provider_for_user(db, user)
    except LLMError as exc:
        msg = Message(conversation_id=conversation.id, role="assistant", content=f"⚠️ {exc}")
        db.add(msg)
        db.commit()
        _log_activity(db, user.id, "chat", "failed", output_data=str(exc))
        return {"new_messages": [msg], "pending_action": None}

    return await _run_loop(db, user, conversation, provider)


async def resume_turn(db: Session, user: User, conversation: Conversation, pending: PendingAction, approve: bool) -> dict:
    """Resolve a pending approval (approve or deny), execute (or skip) the
    tool, and continue the agent loop."""
    if approve:
        try:
            ctx = ToolContext(db=db, user_id=user.id)
            result = execute_tool(pending.tool_name, pending.tool_input, ctx)
            status = "success"
        except (ToolError, TypeError) as exc:
            result = {"error": str(exc)}
            status = "failed"
        pending.status = "approved"
    else:
        result = {"error": "The user denied this action."}
        status = "denied"
        pending.status = "denied"

    from datetime import UTC, datetime

    pending.resolved_at = datetime.now(UTC)

    # Fill in the placeholder tool-result message created when the pending action was raised.
    placeholder = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id, Message.tool_use_id == pending.tool_use_id, Message.role == "tool")
        .first()
    )
    if placeholder:
        placeholder.content = json.dumps(result)

    _log_activity(
        db,
        user.id,
        "approval",
        status,
        tool_name=pending.tool_name,
        input_data=pending.tool_input,
        output_data=result,
    )
    db.commit()

    # If another tool call from the same assistant turn is still awaiting approval, pause again.
    other_pending = (
        db.query(PendingAction)
        .filter(PendingAction.conversation_id == conversation.id, PendingAction.status == "pending")
        .first()
    )
    if other_pending:
        return {"new_messages": [], "pending_action": other_pending}

    try:
        provider = _provider_for_user(db, user)
    except LLMError as exc:
        msg = Message(conversation_id=conversation.id, role="assistant", content=f"⚠️ {exc}")
        db.add(msg)
        db.commit()
        return {"new_messages": [msg], "pending_action": None}

    db.refresh(conversation)
    return await _run_loop(db, user, conversation, provider)


async def _run_loop(db: Session, user: User, conversation: Conversation, provider) -> dict:
    new_messages: list[Message] = []

    for _ in range(MAX_ITERATIONS):
        db.refresh(conversation)
        canonical_messages = _load_canonical_messages(conversation)

        try:
            response = await provider.chat(SYSTEM_PROMPT, canonical_messages, CANONICAL_TOOLS)
        except Exception as exc:  # noqa: BLE001
            logger.exception("LLM call failed")
            msg = Message(conversation_id=conversation.id, role="assistant", content=f"⚠️ I hit an error talking to the AI model: {exc}")
            db.add(msg)
            db.commit()
            _log_activity(db, user.id, "chat", "failed", output_data=str(exc))
            new_messages.append(msg)
            return {"new_messages": new_messages, "pending_action": None}

        if not response.tool_calls:
            msg = Message(conversation_id=conversation.id, role="assistant", content=response.text)
            db.add(msg)
            db.commit()
            new_messages.append(msg)
            _log_activity(db, user.id, "chat", "success", output_data={"reply": response.text[:500]})
            return {"new_messages": new_messages, "pending_action": None}

        assistant_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=response.text,
            tool_calls=[{"id": tc.id, "name": tc.name, "input": tc.input} for tc in response.tool_calls],
        )
        db.add(assistant_msg)
        db.commit()
        new_messages.append(assistant_msg)

        pending_action: PendingAction | None = None

        for tc in response.tool_calls:
            try:
                tool = get_tool(tc.name)
            except ToolError as exc:
                tool_msg = Message(
                    conversation_id=conversation.id,
                    role="tool",
                    tool_use_id=tc.id,
                    tool_name=tc.name,
                    content=json.dumps({"error": str(exc)}),
                )
                db.add(tool_msg)
                db.commit()
                new_messages.append(tool_msg)
                _log_activity(db, user.id, "tool_call", "failed", tool_name=tc.name, input_data=tc.input, output_data=str(exc))
                continue

            if tool.requires_approval:
                pa = PendingAction(
                    conversation_id=conversation.id,
                    user_id=user.id,
                    tool_name=tc.name,
                    tool_input=tc.input,
                    tool_use_id=tc.id,
                    status="pending",
                )
                db.add(pa)
                tool_msg = Message(conversation_id=conversation.id, role="tool", tool_use_id=tc.id, tool_name=tc.name, content="")
                db.add(tool_msg)
                db.commit()
                new_messages.append(tool_msg)
                _log_activity(db, user.id, "tool_call", "pending", tool_name=tc.name, input_data=tc.input, output_data="Awaiting user approval")
                pending_action = pa
                continue

            try:
                ctx = ToolContext(db=db, user_id=user.id)
                result = execute_tool(tc.name, tc.input, ctx)
                status = "success"
                output: dict | str = result
            except ToolError as exc:
                result = {"error": str(exc)}
                status = "failed"
                output = str(exc)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Tool '%s' raised an unexpected error", tc.name)
                result = {"error": f"Tool '{tc.name}' failed unexpectedly: {exc}"}
                status = "failed"
                output = str(exc)

            tool_msg = Message(conversation_id=conversation.id, role="tool", tool_use_id=tc.id, tool_name=tc.name, content=json.dumps(result))
            db.add(tool_msg)
            db.commit()
            new_messages.append(tool_msg)
            _log_activity(db, user.id, "tool_call", status, tool_name=tc.name, input_data=tc.input, output_data=output)

        if pending_action is not None:
            return {"new_messages": new_messages, "pending_action": pending_action}

        # All tool calls resolved without needing approval - loop again so the
        # model can see the tool results and produce its next message.

    timeout_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content="I've taken several steps but haven't finished yet - let me know if you'd like me to continue.",
    )
    db.add(timeout_msg)
    db.commit()
    new_messages.append(timeout_msg)
    return {"new_messages": new_messages, "pending_action": None}
