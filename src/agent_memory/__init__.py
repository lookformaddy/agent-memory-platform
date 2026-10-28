"""agent_memory: persistent memory platform for AI agents.

Episodic, semantic and procedural memory with scoped retrieval, redaction,
scoring/decay, consolidation and conflict supersession.
"""
from .models import (AuditEntry, EpisodicRecord, MemoryType, ProceduralSkill,
                     Scope, SemanticFact)
from .service import MemoryService
from .stores import InMemoryStore, JsonFileStore

__all__ = [
    "AuditEntry", "EpisodicRecord", "MemoryType", "ProceduralSkill", "Scope",
    "SemanticFact", "MemoryService", "InMemoryStore", "JsonFileStore",
]
__version__ = "0.1.0"
