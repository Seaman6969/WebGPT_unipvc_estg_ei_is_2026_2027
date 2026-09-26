from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from chat.modes import DEFAULT as DEFAULT_MODE
from utils.errors import Error

SESSIONS_DIR: Path = Path.home() / ".webgpt" / "sessions"
SESSIONS_ENCODING: str = "utf-8"
DEFAULT_TITLE: str = "New chat"
TITLE_MAX_CHARS: int = 40

_DEFAULT_TITLE_PATTERN: re.Pattern[str] = re.compile(
    rf"^{re.escape(DEFAULT_TITLE)}(?:\s+\d+)?$"
)

@dataclass
class SessionMeta:
    id: str
    title: str
    created_at: str
    updated_at: str

@dataclass
class Session:
    meta: SessionMeta
    messages: list[dict[str, str]] = field(default_factory=list)
    modes: list[str] = field(default_factory=list)

def set_modes(session_id: str, modes: list[str]) -> Error | None:
    session: Session | Error = load_session(session_id=session_id)
    if isinstance(session, Error):
        return session
    session.modes = list(modes) or [DEFAULT_MODE]
    return save_session(session=session)

def ensure_dir() -> Path:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return SESSIONS_DIR

def list_sessions() -> list[SessionMeta]:
    return sorted(
        [_meta_helper(path=p) for p in _files_helper()],
        key=lambda m: m.updated_at,
        reverse=True,
    )

def create_session() -> Session:
    now: str = _now_helper()
    meta = SessionMeta(
        id=uuid.uuid4().hex[:12],
        title=_next_default_title_helper(),
        created_at=now,
        updated_at=now,
    )
    session = Session(meta=meta,modes=[DEFAULT_MODE])
    save_session(session=session)
    return session

def load_session(session_id: str) -> Session | Error:
    path: Path = _path_helper(session_id=session_id)
    if not path.exists():
        return Error(message=f"session not found: {session_id}")
    return _read_helper(path=path)

def save_session(session: Session) -> Error | None:
    ensure_dir()
    session.meta.updated_at = _now_helper()
    return _write_helper(path=_path_helper(session_id=session.meta.id), session=session)

def delete_session(session_id: str) -> Error | None:
    try:
        _path_helper(session_id=session_id).unlink(missing_ok=True)
    except OSError as exc:
        return Error(message=str(exc))
    return None

def rename_session(session_id: str, title: str) -> Error | None:
    session: Session | Error = load_session(session_id=session_id)
    if isinstance(session, Error):
        return session
    session.meta.title = title
    return save_session(session=session)

def append_message(session_id: str, role: str, content: str) -> Error | None:
    session: Session | Error = load_session(session_id=session_id)
    if isinstance(session, Error):
        return session
    session.messages.append({"role": role, "content": content})
    if role == "user" and _is_default_title_helper(title=session.meta.title):
        session.meta.title = _title_helper(content=content)
    return save_session(session=session)

def clear_messages(session_id: str) -> Error | None:
    session: Session | Error = load_session(session_id=session_id)
    if isinstance(session, Error):
        return session
    session.messages = []
    session.meta.title = _next_default_title_helper(exclude_id=session.meta.id)
    return save_session(session=session)

def _path_helper(session_id: str) -> Path:
    return SESSIONS_DIR / f"{session_id}.json"

def _files_helper() -> list[Path]:
    return list(SESSIONS_DIR.glob("*.json")) if SESSIONS_DIR.exists() else []

def _meta_helper(path: Path) -> SessionMeta:
    data: dict = _raw_helper(path=path)
    return _meta_from_helper(data=data, fallback_id=path.stem)

def _meta_from_helper(data: dict, fallback_id: str) -> SessionMeta:
    return SessionMeta(
        id=data.get("id", fallback_id),
        title=data.get("title", DEFAULT_TITLE),
        created_at=data.get("created_at", ""),
        updated_at=data.get("updated_at", ""),
    )

def _read_helper(path: Path) -> Session | Error:
    data: dict = _raw_helper(path=path)
    if not data:
        return Error(message=f"could not read session: {path.name}")
    return Session(
        meta=_meta_from_helper(data=data, fallback_id=path.stem),
        messages=data.get("messages", []),
        modes=data.get("modes", []),
    )

def _raw_helper(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding=SESSIONS_ENCODING))
    except (OSError, json.JSONDecodeError):
        return {}

def _write_helper(path: Path, session: Session) -> Error | None:
    payload: dict = {
        "id": session.meta.id,
        "title": session.meta.title,
        "created_at": session.meta.created_at,
        "updated_at": session.meta.updated_at,
        "messages": session.messages,
        "modes": session.modes,
    }
    try:
        path.write_text(json.dumps(payload, indent=2), encoding=SESSIONS_ENCODING)
    except OSError as exc:
        return Error(message=str(exc))
    return None

def _now_helper() -> str:
    return datetime.now(tz=timezone.utc).isoformat()

def _title_helper(content: str) -> str:
    return content.strip().replace("\n", " ")[:TITLE_MAX_CHARS] or DEFAULT_TITLE

def _next_default_title_helper(exclude_id: str | None = None) -> str:
    used: set[str] = {
        meta.title
        for meta in list_sessions()
        if exclude_id is None or meta.id != exclude_id
    }
    if DEFAULT_TITLE not in used:
        return DEFAULT_TITLE
    index: int = 2
    while f"{DEFAULT_TITLE} {index}" in used:
        index += 1
    return f"{DEFAULT_TITLE} {index}"

def _is_default_title_helper(title: str) -> bool:
    return _DEFAULT_TITLE_PATTERN.match(title) is not None

