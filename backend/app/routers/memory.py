from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import MemoryItem, User
from app.schemas import MemoryItemIn, MemoryItemOut

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("", response_model=list[MemoryItemOut])
def list_memory(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (
        db.query(MemoryItem)
        .filter(MemoryItem.user_id == user.id)
        .order_by(MemoryItem.updated_at.desc())
        .all()
    )


@router.post("", response_model=MemoryItemOut)
def upsert_memory(payload: MemoryItemIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = (
        db.query(MemoryItem)
        .filter(MemoryItem.user_id == user.id, MemoryItem.key == payload.key, MemoryItem.category == payload.category)
        .first()
    )
    if item:
        item.value = payload.value
    else:
        item = MemoryItem(user_id=user.id, category=payload.category, key=payload.key, value=payload.value)
        db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
def delete_memory(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.query(MemoryItem).filter(MemoryItem.id == item_id, MemoryItem.user_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Memory item not found")
    db.delete(item)
    db.commit()
    return None
