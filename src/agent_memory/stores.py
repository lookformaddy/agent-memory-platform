"""Stores: in-memory store plus a JSON file store for persistence.

The JSON store serialises the same dataclasses, so swapping backends does not
change service behaviour. Datetimes round-trip as ISO-8601 strings.
"""
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path

from .models import (AuditEntry, EpisodicRecord, ProceduralSkill, Scope,
                     SemanticFact)


def _encode(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Scope):
        return asdict(obj)
    if is_dataclass(obj):
        return asdict(obj)
    raise TypeError(f"not serialisable: {type(obj)!r}")


def _scope(data: dict) -> Scope:
    return Scope(**data)


class InMemoryStore:
    """Thread-unsafe, single-process store — the default for tests and demos."""

    def __init__(self) -> None:
        self.episodic: dict[str, EpisodicRecord] = {}
        self.facts: dict[str, SemanticFact] = {}
        self.skills: dict[str, ProceduralSkill] = {}
        self.audit: list[AuditEntry] = []

    # -- generic helpers -------------------------------------------------
    @staticmethod
    def _in_scope(record_scope: Scope, scope: Scope) -> bool:
        return record_scope == scope

    def episodic_for(self, scope: Scope) -> list[EpisodicRecord]:
        return [r for r in self.episodic.values() if self._in_scope(r.scope, scope)]

    def facts_for(self, scope: Scope, active_only: bool = True) -> list[SemanticFact]:
        facts = [f for f in self.facts.values() if self._in_scope(f.scope, scope)]
        return [f for f in facts if f.is_active] if active_only else facts

    def skills_for(self, scope: Scope) -> list[ProceduralSkill]:
        return [s for s in self.skills.values() if self._in_scope(s.scope, scope)]

    def audit_for(self, scope: Scope) -> list[AuditEntry]:
        return [a for a in self.audit if self._in_scope(a.scope, scope)]

    def delete_episodic(self, record_id: str) -> bool:
        return self.episodic.pop(record_id, None) is not None


class JsonFileStore(InMemoryStore):
    """Persists the in-memory collections to a single JSON file."""

    def __init__(self, path: str | Path) -> None:
        super().__init__()
        self.path = Path(path)

    def save(self) -> None:
        payload = {
            "episodic": [asdict(r) for r in self.episodic.values()],
            "facts": [asdict(f) for f in self.facts.values()],
            "skills": [asdict(s) for s in self.skills.values()],
            "audit": [asdict(a) for a in self.audit],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, default=_encode, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "JsonFileStore":
        store = cls(path)
        if not store.path.exists():
            return store
        raw = json.loads(store.path.read_text(encoding="utf-8"))
        for item in raw.get("episodic", []):
            item["scope"] = _scope(item["scope"])
            item["created_at"] = datetime.fromisoformat(item["created_at"])
            store.episodic[item["id"]] = EpisodicRecord(**item)
        for item in raw.get("facts", []):
            item["scope"] = _scope(item["scope"])
            item["created_at"] = datetime.fromisoformat(item["created_at"])
            item["superseded_at"] = (datetime.fromisoformat(item["superseded_at"])
                                     if item.get("superseded_at") else None)
            store.facts[item["id"]] = SemanticFact(**item)
        for item in raw.get("skills", []):
            item["scope"] = _scope(item["scope"])
            item["created_at"] = datetime.fromisoformat(item["created_at"])
            item["updated_at"] = datetime.fromisoformat(item["updated_at"])
            store.skills[item["id"]] = ProceduralSkill(**item)
        for item in raw.get("audit", []):
            item["scope"] = _scope(item["scope"])
            item["created_at"] = datetime.fromisoformat(item["created_at"])
            store.audit.append(AuditEntry(**item))
        return store
