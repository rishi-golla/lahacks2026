from __future__ import annotations

from dataclasses import dataclass, field

from .models import HistoryEvent, LinkedGoogleUser, PendingGoogleAction


@dataclass
class GoogleStateStore:
    active_user: LinkedGoogleUser | None = None
    history_events: list[HistoryEvent] = field(default_factory=list)
    pending_action: PendingGoogleAction | None = None

    def get_active_user(self) -> LinkedGoogleUser | None:
        return self.active_user

    def set_active_user(self, user: LinkedGoogleUser) -> None:
        self.active_user = user

    def clear_active_user(self) -> None:
        self.active_user = None

    def get_history(self) -> list[HistoryEvent]:
        return list(self.history_events)

    def append_history(self, event: HistoryEvent) -> None:
        self.history_events.append(event)

    def get_pending_action(self) -> PendingGoogleAction | None:
        return self.pending_action

    def set_pending_action(self, pending_action: PendingGoogleAction) -> None:
        self.pending_action = pending_action

    def clear_pending_action(self) -> None:
        self.pending_action = None

    def reset(self) -> None:
        self.active_user = None
        self.history_events.clear()
        self.pending_action = None


google_state_store = GoogleStateStore()
