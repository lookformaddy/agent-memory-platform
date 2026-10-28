"""Optional FastAPI layer over MemoryService.

Kept separate from the core package so the core stays stdlib-only. Importing
this module requires FastAPI; tests and app.py skip gracefully without it.
"""
from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .models import Scope
from .service import MemoryService

service = MemoryService()


class EpisodicIn(BaseModel):
    tenant_id: str
    user_id: str
    agent_id: str
    content: str
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: list[str] = []


class FactIn(BaseModel):
    tenant_id: str
    user_id: str
    agent_id: str
    subject: str
    predicate: str
    object: str
    confidence: float = Field(ge=0.0, le=1.0)


def create_app() -> FastAPI:
    app = FastAPI(title="Agent Memory Platform", version="0.1.0")

    @app.post("/episodic")
    def create_episodic(payload: EpisodicIn):
        scope = Scope(payload.tenant_id, payload.user_id, payload.agent_id)
        record = service.record_episodic(scope, payload.content,
                                         payload.importance, payload.tags)
        return {"id": record.id, "content": record.content}

    @app.post("/facts")
    def create_fact(payload: FactIn):
        scope = Scope(payload.tenant_id, payload.user_id, payload.agent_id)
        fact = service.add_fact(scope, payload.subject, payload.predicate,
                                payload.object, payload.confidence)
        return {"id": fact.id, "active": fact.is_active}

    @app.get("/retrieve")
    def retrieve(tenant_id: str, user_id: str, agent_id: str,
                 query: str | None = None, limit: int = 20):
        scope = Scope(tenant_id, user_id, agent_id)
        result = service.retrieve(scope, query, limit)
        return {
            "episodic": [r.content for r in result["episodic"]],
            "semantic": [f.object for f in result["semantic"]],
            "procedural": [s.name for s in result["procedural"]],
        }

    @app.post("/consolidate")
    def consolidate(tenant_id: str, user_id: str, agent_id: str):
        scope = Scope(tenant_id, user_id, agent_id)
        facts = service.consolidate(scope)
        return {"created_facts": len(facts)}

    return app


app = create_app()
