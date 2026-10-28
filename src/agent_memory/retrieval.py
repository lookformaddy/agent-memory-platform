"""Scoped retrieval: exact-scope isolation, ranked results.

Every retrieval function takes a Scope and returns only records in that exact
scope. Results are ranked by combined importance/recency score (episodic),
confidence (facts), or success rate (skills).
"""
from __future__ import annotations

from datetime import datetime, timezone

from .models import (EpisodicRecord, ProceduralSkill, Scope, SemanticFact)
from .scoring import combined_score
from .stores import InMemoryStore


def _matches(query: str | None, text: str) -> bool:
    return query is None or query.lower() in text.lower()


def retrieve_episodic(store: InMemoryStore, scope: Scope,
                      query: str | None = None, limit: int = 20,
                      now: datetime | None = None) -> list[EpisodicRecord]:
    now = now or datetime.now(timezone.utc)
    records = [r for r in store.episodic_for(scope)
               if _matches(query, r.content)]
    records.sort(key=lambda r: combined_score(r.importance, r.created_at, now),
                 reverse=True)
    return records[:limit]


def retrieve_facts(store: InMemoryStore, scope: Scope,
                   query: str | None = None, limit: int = 20) -> list[SemanticFact]:
    facts = [f for f in store.facts_for(scope)
             if _matches(query, f"{f.subject} {f.predicate} {f.object}")]
    facts.sort(key=lambda f: (f.confidence, f.created_at), reverse=True)
    return facts[:limit]


def retrieve_skills(store: InMemoryStore, scope: Scope,
                    query: str | None = None, limit: int = 20) -> list[ProceduralSkill]:
    skills = [s for s in store.skills_for(scope)
              if _matches(query, f"{s.name} {s.description}")]
    skills.sort(key=lambda s: (s.success_rate, s.usage_count), reverse=True)
    return skills[:limit]


def resolve_active_facts(facts: list[SemanticFact]) -> list[SemanticFact]:
    """For each (subject, predicate), keep only the newest highest-confidence fact.

    This is a defensive second layer: the service already supersedes on write,
    but retrieval through this function can never surface two live versions
    of the same claim.
    """
    best: dict[tuple[str, str], SemanticFact] = {}
    for fact in facts:
        if not fact.is_active:
            continue
        key = (fact.subject, fact.predicate)
        current = best.get(key)
        if current is None or (fact.confidence, fact.created_at) > (
                current.confidence, current.created_at):
            best[key] = fact
    return sorted(best.values(), key=lambda f: f.confidence, reverse=True)
