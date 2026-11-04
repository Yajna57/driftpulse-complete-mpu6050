from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import GLOBAL_SCOPE, TelegramConfig, utc_now
from ..services.telegram import get_bot_token, get_config, send_message

router = APIRouter(prefix="/api/v1/settings/telegram", tags=["telegram"])

CHAT_ID_RE = re.compile(r"^(-?\d{5,20}|@[A-Za-z][A-Za-z0-9_]{4,31})$")
TOKEN_RE = re.compile(r"^\d{5,15}:[A-Za-z0-9_-]{20,60}$")


class ChatIn(BaseModel):
    chat_id: str | None = None
    enabled: bool = True

    @field_validator("chat_id")
    @classmethod
    def _check_chat(cls, value: str | None) -> str | None:
        value = (value or "").strip()
        if not value:
            return None
        if not CHAT_ID_RE.match(value):
            raise ValueError("Chat id must be a number (e.g. 987654321, -100123...) or @channelname")
        return value


class GeneralIn(ChatIn):
    # None = keep the saved token. Empty string = clear it.
    bot_token: str | None = None

    @field_validator("bot_token")
    @classmethod
    def _check_token(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if value and not TOKEN_RE.match(value):
            raise ValueError("Bot token looks wrong. Copy it from @BotFather (format 123456:ABC...)")
        return value


class TestIn(BaseModel):
    user_id: str | None = None  # None = test the general chat


def _chat_out(row: TelegramConfig | None) -> dict:
    return {"chat_id": row.chat_id if row else None, "enabled": row.enabled if row else True}


def _mask(token: str) -> str:
    return f"{token.split(':')[0]}:••••{token[-4:]}" if token else ""


def _read(db: Session, user_id: str | None) -> dict:
    token = get_bot_token(db)
    return {
        "bot_token_set": bool(token),
        "bot_token_hint": _mask(token),
        "general": _chat_out(get_config(db, GLOBAL_SCOPE)),
        "user": _chat_out(get_config(db, user_id)) if user_id else None,
    }


def _upsert(db: Session, scope: str) -> TelegramConfig:
    row = get_config(db, scope)
    if row is None:
        row = TelegramConfig(scope=scope)
        db.add(row)
    row.updated_at = utc_now()
    return row


@router.get("")
def read_settings(user_id: str | None = None, db: Session = Depends(get_db)) -> dict:
    return _read(db, user_id)


@router.put("/general")
def save_general(payload: GeneralIn, db: Session = Depends(get_db)) -> dict:
    row = _upsert(db, GLOBAL_SCOPE)
    row.chat_id = payload.chat_id
    row.enabled = payload.enabled
    if payload.bot_token is not None:
        row.bot_token = payload.bot_token or None
    db.commit()
    return _read(db, None)


@router.put("/users/{user_id}")
def save_user(user_id: str, payload: ChatIn, db: Session = Depends(get_db)) -> dict:
    if user_id == GLOBAL_SCOPE:
        raise HTTPException(status_code=400, detail="Invalid user id")
    row = _upsert(db, user_id)
    row.chat_id = payload.chat_id
    row.enabled = payload.enabled
    db.commit()
    return _read(db, user_id)


@router.post("/test")
def send_test(payload: TestIn, db: Session = Depends(get_db)) -> dict:
    token = get_bot_token(db)
    if not token:
        raise HTTPException(status_code=400, detail="Save a bot token first.")
    row = get_config(db, payload.user_id or GLOBAL_SCOPE)
    if row is None or not row.chat_id:
        raise HTTPException(status_code=400, detail="Save a chat id first.")
    who = payload.user_id or "general chat"
    try:
        send_message(token, row.chat_id, f"DriftPulse test message for {who}. Telegram alerts are working.")
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    return {"sent": True}
