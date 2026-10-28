"""Consolidation: episodic records -> semantic facts.

Groups an agent's episodic records by topic (first tag, or "general") and,
for any topic with at least `min_count` records, emits one semantic fact
whose provenance lists every contributing record id. Consolidation never
deletes the source records — the audit trail stays intact.
"""
from __future__ import annotations

from collections import defaultdict

from .models import EpisodicRecord, Scope, SemanticFact, new_id, utcnow


def consolidate_episodic(records: list[EpisodicRecord],
                         min_count: int = 2) -> list[SemanticFact]:
    """Return one fact per qualifying (scope, topic) group."""
    groups: dict[tuple[Scope, str], list[EpisodicRecord]] = defaultdict(list)
    for record in records:
        topic = record.tags[0] if record.tags else "general"
        groups[(record.scope, topic)].append(record)

    facts: list[SemanticFact] = []
    for (scope, topic), group in sorted(groups.items(), key=lambda kv: kv[0][1]):
        if len(group) < min_count:
            continue
        avg_importance = sum(r.importance for r in group) / len(group)
        confidence = round(min(0.95, 0.5 + 0.1 * len(group)), 2)
        facts.append(SemanticFact(
            id=new_id("fact"),
            scope=scope,
            subject=f"agent:{scope.agent_id}",
            predicate="observed_pattern",
            object=f"{len(group)} interactions about '{topic}' "
                   f"(avg importance {avg_importance:.2f})",
            confidence=confidence,
            created_at=utcnow(),
            provenance_ids=[r.id for r in group],
        ))
    return facts
