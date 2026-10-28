"""Core data models for the agent memory platform.

All models are plain typed dataclasses with no external dependencies, so the
core logic is testable and portable. Timestamps are timezone-aware UTC.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class MemoryType(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


@dataclass(frozen=True)
class Scope:
    """Isolation boundary for every record.

    Retrieval matches a scope exactly: a record is visible only to the same
    tenant + user + agent combination that wrote it. There is no wildcard
    or cross-scope fallback, by design.
    """

    tenant_id: str
    user_id: str
    agent_id: str

    def key(self) -> tuple[str, str, str]:
        return (self.tenant_id, self.user_id, self.agent_id)


@dataclass
class EpisodicRecord:
    """A timestamped interaction record: what happened, when, how important."""

    id: str
    scope: Scope
    content: str
    created_at: datetime
    importance: float = 0.5
    tags: list[str] = field(default_factory=list)
    source: str = "agent"

    def __post_init__(self) -> None:
        if not 0.0 <= self.importance <= 1.0:
            raise ValueError("importance must be in [0, 1]")


@dataclass
class SemanticFact:
    """A durable fact distilled from experience, with confidence + provenance."""

    id: str
    scope: Scope
    subject: str
    predicate: str
    object: str
    confidence: float
    created_at: datetime
    provenance_ids: list[str] = field(default_factory=list)
    superseded_by: str | None = None
    superseded_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        return self.superseded_by is None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")


@dataclass
class ProceduralSkill:
    """A reusable routine: named steps plus a success-rate track record."""

    id: str
    scope: Scope
    name: str
    description: str
    steps: list[str]
    created_at: datetime
    updated_at: datetime
    usage_count: int = 0
    success_count: int = 0

    @property
    def success_rate(self) -> float:
        if self.usage_count == 0:
            return 0.0
        return self.success_count / self.usage_count


@dataclass
class AuditEntry:
    """Immutable-ish log line for supersession, consolidation and pruning."""

    id: str
    scope: Scope
    action: str  # created | superseded | consolidated | pruned | skill_used
    record_id: str
    created_at: datetime
    detail: str = ""
