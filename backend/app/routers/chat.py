from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agent.agent import resume_turn, start_turn
from app.database import get_db
from app.deps import get_current_user
from app.models import Conversation, Message, PendingAction, User
from app.schemas import (
    ApprovalDecision,
    ChatRequest,
    ChatResponse,
    ConversationDetail,
    ConversationOut,
    MessageOut,
    PendingActionOut,
)

router = APIRouter(prefix="/api", tags=["chat"])


def _get_conversation(db: Session, user: User, conversation_id: int) -> Conversation:
    convo = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == user.id)
        .first()
    )
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return convo


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    convos = (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    return convos


@router.post("/conversations", response_model=ConversationOut)
def create_conversation(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    convo = Conversation(user_id=user.id, title="New conversation")
    db.add(convo)
    db.commit()
    db.refresh(convo)
    return convo


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    convo = _get_conversation(db, user, conversation_id)
    return convo


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    convo = _get_conversation(db, user, conversation_id)
    db.delete(convo)
    db.commit()
    return None


def _maybe_set_title(convo: Conversation, user_message: str) -> None:
    if convo.title == "New conversation":
        convo.title = user_message.strip()[:60] or "New conversation"


def _build_chat_response(convo: Conversation, result: dict) -> ChatResponse:
    pending = result.get("pending_action")
    return ChatResponse(
        conversation_id=convo.id,
        messages=[MessageOut.model_validate(m) for m in result["new_messages"]],
        pending_action=PendingActionOut.model_validate(pending) if pending else None,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if payload.conversation_id is not None:
        convo = _get_conversation(db, user, payload.conversation_id)
    else:
        convo = Conversation(user_id=user.id, title="New conversation")
        db.add(convo)
        db.commit()
        db.refresh(convo)

    _maybe_set_title(convo, payload.message)
    db.commit()

    result = await start_turn(db, user, convo, payload.message)
    return _build_chat_response(convo, result)


@router.post("/conversations/{conversation_id}/messages", response_model=ChatResponse)
async def send_message(
    conversation_id: int,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    convo = _get_conversation(db, user, conversation_id)
    _maybe_set_title(convo, payload.message)
    db.commit()

    result = await start_turn(db, user, convo, payload.message)
    return _build_chat_response(convo, result)


@router.post("/conversations/{conversation_id}/approvals/{action_id}", response_model=ChatResponse)
async def resolve_approval(
    conversation_id: int,
    action_id: int,
    payload: ApprovalDecision,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    convo = _get_conversation(db, user, conversation_id)
    pending = (
        db.query(PendingAction)
        .filter(PendingAction.id == action_id, PendingAction.conversation_id == convo.id, PendingAction.user_id == user.id)
        .first()
    )
    if not pending:
        raise HTTPException(status_code=404, detail="Pending action not found")
    if pending.status != "pending":
        raise HTTPException(status_code=400, detail="This action has already been resolved")

    result = await resume_turn(db, user, convo, pending, payload.approve)
    return _build_chat_response(convo, result)
