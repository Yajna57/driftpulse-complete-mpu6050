from __future__ import annotations

import html
import logging
import threading

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import GLOBAL_SCOPE, TelegramConfig

log = logging.getLogger(__name__)
settings = get_settings()

PENDING_KEY = "telegram_pending"

ACTIONS = {
    "ELEVATED": [
        "Sit down and rest for 10-15 minutes.",
        "Drink water.",
        "Check that the sensors are seated and the ECG electrodes are attached.",
        "Watch the next readings. If still elevated after 15 minutes, contact a doctor.",
    ],
    "ALERT": [
        "Stop activity and rest now.",
        "Check sensor placement to rule out a bad signal.",
        "If you have chest pain, dizziness or shortness of breath, call emergency services now.",
        "Otherwise contact a doctor today and share this alert.",
    ],
}

METRIC_LABEL = {
    "heart_rate_bpm": ("Heart rate", "bpm"),
    "rmssd_ms": ("RMSSD", "ms"),
    "sdnn_ms": ("SDNN", "ms"),
    "temperature_c": ("Temperature", "°C"),
}


def build_alert_message(
    user_id: str,
    severity: str,
    summary: str,
    observations: list[str],
    z_scores: dict[str, float | None],
    values: dict[str, float | None],
    activity: str,
    risk_score: int,
) -> str:
    esc = html.escape
    lines = [
        f"<b>DriftPulse alert: {esc(severity)}</b>",
        f"User: {esc(user_id)}",
        f"Risk score: {risk_score}/100",
        f"Activity: {esc(activity)}",
        "",
        esc(summary),
        "",
        "<b>Readings (z-score vs your baseline)</b>",
    ]
    for key, (label, unit) in METRIC_LABEL.items():
        value, z = values.get(key), z_scores.get(key)
        if value is None:
            continue
        suffix = f" (z={z:+.1f})" if z is not None else ""
        lines.append(f"- {label}: {value:.1f} {unit}{suffix}")
    lines += ["", "<b>Why</b>"] + [f"- {esc(o)}" for o in observations]
    lines += ["", "<b>What to do</b>"]
    lines += [f"{i}. {esc(a)}" for i, a in enumerate(ACTIONS.get(severity, []), 1)]
    lines += ["", "<i>Educational prototype. Not a medical diagnosis.</i>"]
    return "\n".join(lines)


def get_config(db: Session, scope: str) -> TelegramConfig | None:
    return db.scalar(select(TelegramConfig).where(TelegramConfig.scope == scope))


def get_bot_token(db: Session) -> str:
    row = get_config(db, GLOBAL_SCOPE)
    if row is not None and row.bot_token:
        return row.bot_token
    return settings.telegram_bot_token


def resolve_chat_ids(db: Session, user_id: str) -> list[str]:
    """Per-user chat plus the general chat, without duplicates."""
    chats: list[str] = []
    for scope in (user_id, GLOBAL_SCOPE):
        row = get_config(db, scope)
        if row is not None and row.enabled and row.chat_id and row.chat_id not in chats:
            chats.append(row.chat_id)
    return chats


def send_message(token: str, chat_id: str, text: str) -> None:
    """Send one message. Raises RuntimeError with a readable reason on failure."""
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
    except requests.RequestException as exc:
        # Do not include the exception text: it can contain the URL with the token.
        raise RuntimeError(f"Network error ({type(exc).__name__})") from None
    if not response.ok:
        try:
            detail = response.json().get("description", response.reason)
        except ValueError:
            detail = response.reason
        raise RuntimeError(f"Telegram rejected the message: {detail}")


def _send_all(token: str, chat_ids: list[str], text: str) -> None:
    for chat_id in chat_ids:
        try:
            send_message(token, chat_id, text)
        except RuntimeError as exc:
            log.warning("telegram send to %s failed: %s", chat_id, exc)


def queue_alert(db: Session, user_id: str, text: str) -> None:
    """Hold the message until the alert row is committed."""
    db.info.setdefault(PENDING_KEY, []).append((user_id, text))


def flush_pending(db: Session) -> None:
    """Call after db.commit(). Sends queued messages in background threads."""
    pending = db.info.pop(PENDING_KEY, [])
    if not pending:
        return
    token = get_bot_token(db)
    if not token:
        return
    for user_id, text in pending:
        chat_ids = resolve_chat_ids(db, user_id)
        if chat_ids:
            threading.Thread(target=_send_all, args=(token, chat_ids, text), daemon=True).start()
