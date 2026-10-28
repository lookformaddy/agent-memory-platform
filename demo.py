"""End-to-end demo: record, fact, skill, consolidate, prune, retrieve.

Run:  python3 demo.py   (stdlib only; no server needed)
All data is synthetic and generic.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from agent_memory import MemoryService, Scope  # noqa: E402
from agent_memory.models import EpisodicRecord, new_id  # noqa: E402


def main() -> None:
    service = MemoryService()
    scope = Scope(tenant_id="acme", user_id="user-1", agent_id="support-agent")
    other = Scope(tenant_id="acme", user_id="user-2", agent_id="support-agent")

    # Episodic: one contains a secret-like token that must be redacted.
    service.record_episodic(scope, "User asked about refund policy", 0.8, ["billing"])
    service.record_episodic(scope, "User asked about refund window details", 0.7, ["billing"])
    service.record_episodic(scope, "Debug note: api_key=sk-demo-token-1234567890abcdef", 0.2, ["debug"])
    service.record_episodic(other, "Other user's private note", 0.9, ["billing"])

    # Semantic conflict: newer fact supersedes the older one.
    old = service.add_fact(scope, "refund-policy", "window-days", "14 days", 0.6)
    new = service.add_fact(scope, "refund-policy", "window-days", "30 days", 0.9)

    # Procedural skill with a tracked success rate.
    skill = service.add_skill(scope, "refund-lookup",
                              "Look up a refund window for an order",
                              ["Ask for order id", "Check policy", "Reply with window"])
    service.record_skill_use(skill.id, success=True)
    service.record_skill_use(skill.id, success=True)
    service.record_skill_use(skill.id, success=False)

    facts = service.consolidate(scope)
    # Stale low-importance record, backdated 120 days, gets pruned.
    stale = EpisodicRecord(id=new_id("epi"), scope=scope, content="old trivia",
                           created_at=datetime.now(timezone.utc) - timedelta(days=120),
                           importance=0.1, tags=["trivia"])
    service.store.episodic[stale.id] = stale
    pruned = service.prune(retention_days=90, min_importance=0.3)

    result = service.retrieve(scope, query="refund")
    audit = service.audit_trail(scope)
    print("=== Agent Memory Platform demo ===")
    print(f"episodic retrieved for 'refund': {len(result['episodic'])}")
    print(f"semantic facts retrieved: {len(result['semantic'])} "
          f"(old active={old.is_active}, new active={new.is_active})")
    print(f"procedural skills retrieved: {len(result['procedural'])} "
          f"(refund-lookup success rate: {skill.success_rate:.2f})")
    print(f"consolidated facts created: {len(facts)}")
    print(f"pruned stale records: {pruned}")
    print(f"audit entries for scope: {len(audit)}")
    print(f"cross-scope leak check: other user's note in results? "
          f"{any('Other user' in r.content for r in result['episodic'])}")
    print(f"redaction check: secret stored? "
          f"{any('sk-demo-token' in r.content for r in service.store.episodic.values())}")


if __name__ == "__main__":
    main()
