"""Core CRUD, scoring/decay, consolidation, supersession, isolation, redaction, pruning."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_memory import MemoryService, Scope  # noqa: E402
from agent_memory.models import EpisodicRecord, new_id  # noqa: E402
from agent_memory.redaction import redact  # noqa: E402
from agent_memory.retrieval import resolve_active_facts  # noqa: E402
from agent_memory.scoring import combined_score, is_prunable, recency_score  # noqa: E402
from agent_memory.stores import JsonFileStore  # noqa: E402

SCOPE = Scope("tenant-a", "user-1", "agent-1")
OTHER = Scope("tenant-a", "user-2", "agent-1")
NOW = datetime.now(timezone.utc)


def svc() -> MemoryService:
    return MemoryService()


def test_episodic_crud_and_retrieval():
    s = svc()
    r = s.record_episodic(SCOPE, "User prefers concise summaries", 0.8, ["prefs"])
    assert r.id in s.store.episodic
    assert s.retrieve(SCOPE, query="concise")["episodic"][0].id == r.id


def test_semantic_crud():
    s = svc()
    f = s.add_fact(SCOPE, "user-1", "prefers", "concise summaries", 0.85)
    assert f.is_active
    assert s.retrieve(SCOPE)["semantic"][0].id == f.id


def test_procedural_crud_and_success_rate():
    s = svc()
    skill = s.add_skill(SCOPE, "summarise", "Summarise a thread",
                        ["Read thread", "Draft summary"])
    s.record_skill_use(skill.id, True)
    s.record_skill_use(skill.id, False)
    assert skill.usage_count == 2 and skill.success_rate == 0.5


def test_recency_and_combined_scoring():
    assert recency_score(NOW, NOW) == pytest.approx(1.0)
    old = NOW - timedelta(days=30)
    assert recency_score(old, NOW) == pytest.approx(0.5)
    assert combined_score(1.0, NOW, NOW) > combined_score(0.0, NOW, NOW)


def test_decay_pruning_keeps_important_history():
    s = svc()
    stale_low = EpisodicRecord(id=new_id("epi"), scope=SCOPE, content="trivia",
                               created_at=NOW - timedelta(days=120), importance=0.1)
    stale_high = EpisodicRecord(id=new_id("epi"), scope=SCOPE, content="key decision",
                                created_at=NOW - timedelta(days=120), importance=0.9)
    s.store.episodic[stale_low.id] = stale_low
    s.store.episodic[stale_high.id] = stale_high
    assert is_prunable(0.1, NOW - timedelta(days=120), NOW)
    assert not is_prunable(0.9, NOW - timedelta(days=120), NOW)
    assert s.prune(now=NOW) == 1
    assert stale_high.id in s.store.episodic and stale_low.id not in s.store.episodic


def test_consolidation_creates_fact_with_provenance():
    s = svc()
    s.record_episodic(SCOPE, "Asked about billing", 0.6, ["billing"])
    s.record_episodic(SCOPE, "Asked about billing again", 0.6, ["billing"])
    s.record_episodic(SCOPE, "Unrelated note", 0.6, ["other"])
    facts = s.consolidate(SCOPE)
    assert len(facts) == 1
    assert len(facts[0].provenance_ids) == 2
    assert facts[0].confidence > 0.5


def test_supersession_keeps_audit_trail():
    s = svc()
    old = s.add_fact(SCOPE, "policy", "window", "14 days", 0.6)
    new = s.add_fact(SCOPE, "policy", "window", "30 days", 0.9)
    assert not old.is_active and old.superseded_by == new.id
    assert new.is_active
    assert s.retrieve(SCOPE)["semantic"][0].id == new.id
    actions = [a.action for a in s.audit_trail(SCOPE)]
    assert "superseded" in actions


def test_resolve_active_facts_deduplicates():
    s = svc()
    old = s.add_fact(SCOPE, "policy", "window", "14 days", 0.6)
    s.add_fact(SCOPE, "policy", "window", "30 days", 0.9)
    resolved = resolve_active_facts(s.store.facts_for(SCOPE, active_only=False))
    assert [f.id for f in resolved] != [old.id]
    assert len(resolved) == 1


def test_scoped_retrieval_isolation():
    s = svc()
    s.record_episodic(SCOPE, "User 1 secret preference", 0.9, ["prefs"])
    s.record_episodic(OTHER, "User 2 private note", 0.9, ["prefs"])
    contents = [r.content for r in s.retrieve(SCOPE)["episodic"]]
    assert contents == ["User 1 secret preference"]


def test_redaction_at_write_time():
    s = svc()
    r = s.record_episodic(SCOPE, "Token is Bearer abc123XYZ and email a@example.com", 0.5)
    assert "abc123XYZ" not in r.content and "a@example.com" not in r.content
    assert "[REDACTED]" in r.content
    result = redact("api_key=sk-abcdefghijklmnop1234 and 123-45-6789")
    assert "sk-abcdefghijklmnop" not in result.text
    assert "labelled_secret" in result.redacted_kinds or "sk_token" in result.redacted_kinds


def test_json_store_round_trip(tmp_path):
    s = svc()
    s.record_episodic(SCOPE, "Persist me", 0.7, ["demo"])
    s.add_fact(SCOPE, "x", "is", "y", 0.8)
    path = tmp_path / "mem.json"
    store = JsonFileStore(path)
    store.episodic, store.facts = s.store.episodic, s.store.facts
    store.save()
    loaded = JsonFileStore.load(path)
    assert len(loaded.episodic_for(SCOPE)) == 1
    assert len(loaded.facts_for(SCOPE)) == 1
    assert loaded.episodic_for(SCOPE)[0].content == "Persist me"
