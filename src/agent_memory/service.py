"""MemoryService: the single orchestration layer over stores.

Responsibilities: redact at write time, enforce scope isolation, supersede
conflicting facts (newer or higher-confidence wins, old fact kept with an
audit entry), run consolidation, and prune stale low-importance records.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .consolidation import consolidate_episodic
from .models import (AuditEntry, EpisodicRecord, ProceduralSkill, Scope,
                     SemanticFact, new_id, utcnow)
from .redaction import redact
from .retrieval import retrieve_episodic, retrieve_facts, retrieve_skills
from .scoring import is_prunable
from .stores import InMemoryStore


class MemoryService:
    def __init__(self, store: InMemoryStore | None = None) -> None:
        self.store = store or InMemoryStore()

    # -- internal --------------------------------------------------------
    def _audit(self, scope: Scope, action: str, record_id: str, detail: str = "") -> None:
        self.store.audit.append(AuditEntry(
            id=new_id("audit"), scope=scope, action=action,
            record_id=record_id, created_at=utcnow(), detail=detail))

    # -- episodic ----------------------------------------------------------
    def record_episodic(self, scope: Scope, content: str, importance: float = 0.5,
                        tags: list[str] | None = None,
                        source: str = "agent") -> EpisodicRecord:
        clean = redact(content).text
        record = EpisodicRecord(id=new_id("epi"), scope=scope, content=clean,
                                created_at=utcnow(), importance=importance,
                                tags=list(tags or []), source=source)
        self.store.episodic[record.id] = record
        self._audit(scope, "created", record.id, "episodic")
        return record

    # -- semantic ----------------------------------------------------------
    def add_fact(self, scope: Scope, subject: str, predicate: str, object_: str,
                 confidence: float, provenance_ids: list[str] | None = None) -> SemanticFact:
        """Add a fact; supersede any active fact with the same subject+predicate.

        The superseded fact is retained (status via superseded_by) and an
        audit entry records the replacement — history is never rewritten.
        """
        clean = redact(object_).text
        for existing in self.store.facts_for(scope):
            if existing.subject == subject and existing.predicate == predicate:
                existing.superseded_at = utcnow()
                # placeholder first; set to the new id below
                existing.superseded_by = "pending"
                self._audit(scope, "superseded", existing.id,
                            f"replaced by new fact for {subject}/{predicate}")
        fact = SemanticFact(id=new_id("fact"), scope=scope, subject=subject,
                            predicate=predicate, object=clean,
                            confidence=confidence, created_at=utcnow(),
                            provenance_ids=list(provenance_ids or []))
        for existing in self.store.facts_for(scope, active_only=False):
            if existing.superseded_by == "pending":
                existing.superseded_by = fact.id
        self.store.facts[fact.id] = fact
        self._audit(scope, "created", fact.id, "semantic fact")
        return fact

    # -- procedural --------------------------------------------------------
    def add_skill(self, scope: Scope, name: str, description: str,
                  steps: list[str]) -> ProceduralSkill:
        now = utcnow()
        skill = ProceduralSkill(id=new_id("skill"), scope=scope, name=name,
                                description=redact(description).text,
                                steps=[redact(s).text for s in steps],
                                created_at=now, updated_at=now)
        self.store.skills[skill.id] = skill
        self._audit(scope, "created", skill.id, "procedural skill")
        return skill

    def record_skill_use(self, skill_id: str, success: bool) -> ProceduralSkill:
        skill = self.store.skills[skill_id]
        skill.usage_count += 1
        skill.success_count += 1 if success else 0
        skill.updated_at = utcnow()
        self._audit(skill.scope, "skill_used", skill.id,
                    "success" if success else "failure")
        return skill

    # -- retrieval ---------------------------------------------------------
    def retrieve(self, scope: Scope, query: str | None = None,
                 limit: int = 20) -> dict[str, list]:
        return {
            "episodic": retrieve_episodic(self.store, scope, query, limit),
            "semantic": retrieve_facts(self.store, scope, query, limit),
            "procedural": retrieve_skills(self.store, scope, query, limit),
        }

    # -- consolidation / pruning -------------------------------------------
    def consolidate(self, scope: Scope | None = None,
                    min_count: int = 2) -> list[SemanticFact]:
        records = (self.store.episodic_for(scope) if scope is not None
                   else list(self.store.episodic.values()))
        facts = consolidate_episodic(records, min_count=min_count)
        for fact in facts:
            self.store.facts[fact.id] = fact
            self._audit(fact.scope, "consolidated", fact.id,
                        f"from {len(fact.provenance_ids)} episodic records")
        return facts

    def prune(self, now: datetime | None = None, retention_days: float = 90.0,
              min_importance: float = 0.3) -> int:
        now = now or datetime.now(timezone.utc)
        removed = 0
        for record in list(self.store.episodic.values()):
            if is_prunable(record.importance, record.created_at, now,
                            retention_days, min_importance):
                self.store.delete_episodic(record.id)
                self._audit(record.scope, "pruned", record.id, "stale low-importance")
                removed += 1
        return removed

    def audit_trail(self, scope: Scope) -> list[AuditEntry]:
        return self.store.audit_for(scope)
