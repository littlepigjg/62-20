import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
from dataclasses import dataclass, field, asdict

from ..config import BASE_DIR


SHORTCUTS_DIR = BASE_DIR / "data"
SHORTCUTS_FILE = SHORTCUTS_DIR / "search_shortcuts.json"
HISTORY_FILE = SHORTCUTS_DIR / "search_history.json"

SHORTCUTS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class SearchShortcut:
    id: str
    name: str
    query: str
    filters: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    usage_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchShortcut":
        return cls(**data)


class SearchShortcutManager:
    def __init__(self):
        self._shortcuts: Dict[str, SearchShortcut] = {}
        self._load_shortcuts()

    def _load_shortcuts(self) -> None:
        if SHORTCUTS_FILE.exists():
            try:
                with open(SHORTCUTS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for sid, shortcut_data in data.items():
                    self._shortcuts[sid] = SearchShortcut.from_dict(shortcut_data)
            except Exception:
                self._shortcuts = {}

    def _save_shortcuts(self) -> None:
        data = {}
        for sid, shortcut in self._shortcuts.items():
            data[sid] = shortcut.to_dict()
        with open(SHORTCUTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def list_shortcuts(self) -> List[SearchShortcut]:
        shortcuts = list(self._shortcuts.values())
        shortcuts.sort(key=lambda s: (s.usage_count, s.updated_at), reverse=True)
        return shortcuts

    def get_shortcut(self, shortcut_id: str) -> Optional[SearchShortcut]:
        return self._shortcuts.get(shortcut_id)

    def create_shortcut(
        self,
        name: str,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> SearchShortcut:
        shortcut_id = f"shortcut_{uuid.uuid4().hex[:8]}"
        now = datetime.now().isoformat()
        shortcut = SearchShortcut(
            id=shortcut_id,
            name=name,
            query=query,
            filters=filters or {},
            created_at=now,
            updated_at=now,
            usage_count=0,
        )
        self._shortcuts[shortcut_id] = shortcut
        self._save_shortcuts()
        return shortcut

    def update_shortcut(
        self,
        shortcut_id: str,
        name: Optional[str] = None,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Optional[SearchShortcut]:
        shortcut = self._shortcuts.get(shortcut_id)
        if not shortcut:
            return None

        if name is not None:
            shortcut.name = name
        if query is not None:
            shortcut.query = query
        if filters is not None:
            shortcut.filters = filters

        shortcut.updated_at = datetime.now().isoformat()
        self._save_shortcuts()
        return shortcut

    def delete_shortcut(self, shortcut_id: str) -> bool:
        if shortcut_id in self._shortcuts:
            del self._shortcuts[shortcut_id]
            self._save_shortcuts()
            return True
        return False

    def increment_usage(self, shortcut_id: str) -> None:
        shortcut = self._shortcuts.get(shortcut_id)
        if shortcut:
            shortcut.usage_count += 1
            shortcut.updated_at = datetime.now().isoformat()
            self._save_shortcuts()


class SearchHistoryManager:
    def __init__(self):
        self._history: List[Dict[str, Any]] = []
        self._max_history = 100
        self._load_history()

    def _load_history(self) -> None:
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    self._history = json.load(f)
            except Exception:
                self._history = []

    def _save_history(self) -> None:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(self._history, f, ensure_ascii=False, indent=2)

    def add_search(self, query: str, filters: Optional[Dict[str, Any]] = None) -> None:
        if not query.strip():
            return

        self._history = [h for h in self._history if h["query"].lower() != query.lower()]

        self._history.insert(0, {
            "query": query,
            "filters": filters or {},
            "timestamp": datetime.now().isoformat(),
        })

        if len(self._history) > self._max_history:
            self._history = self._history[:self._max_history]

        self._save_history()

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._history[:limit]

    def clear_history(self) -> None:
        self._history = []
        self._save_history()

    def remove_from_history(self, query: str) -> bool:
        original_len = len(self._history)
        self._history = [h for h in self._history if h["query"] != query]
        if len(self._history) != original_len:
            self._save_history()
            return True
        return False


shortcut_manager = SearchShortcutManager()
history_manager = SearchHistoryManager()
