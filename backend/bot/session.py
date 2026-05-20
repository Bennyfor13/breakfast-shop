"""In-memory conversation session store with TTL-based expiry."""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from enum import Enum, auto


class SessionState(Enum):
    IDLE = auto()
    AWAITING_CONFIRMATION = auto()
    COLLECTING_PARAMS = auto()


@dataclass
class Session:
    user_id: str
    state: SessionState = SessionState.IDLE
    pending_action: str = ""  # e.g. "edit_shift", "assign_replacement"
    pending_params: dict = field(default_factory=dict)
    confirm_message: str = ""  # what to show user before confirmation
    last_active: float = field(default_factory=time.time)
    ttl: int = 1800  # 30 minutes

    def is_expired(self) -> bool:
        return time.time() - self.last_active > self.ttl

    def touch(self):
        self.last_active = time.time()

    def reset(self):
        self.state = SessionState.IDLE
        self.pending_action = ""
        self.pending_params = {}
        self.confirm_message = ""


class SessionStore:
    """In-memory session store keyed by user_id."""

    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def get(self, user_id: str) -> Session:
        self._gc()
        session = self._sessions.get(user_id)
        if session and session.is_expired():
            del self._sessions[user_id]
            session = None
        if not session:
            session = Session(user_id=user_id)
            self._sessions[user_id] = session
        session.touch()
        return session

    def _gc(self):
        expired = [uid for uid, s in self._sessions.items() if s.is_expired()]
        for uid in expired:
            del self._sessions[uid]


# Singleton
session_store = SessionStore()
