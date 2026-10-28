"""FastAPI tests — skipped gracefully when FastAPI is not installed."""
import sys
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")  # TestClient transport (fastapi[standard] stack)

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from agent_memory.api import create_app  # noqa: E402


def test_api_episodic_and_retrieve():
    client = TestClient(create_app())
    resp = client.post("/episodic", json={
        "tenant_id": "t1", "user_id": "u1", "agent_id": "a1",
        "content": "API smoke note", "importance": 0.7, "tags": ["smoke"]})
    assert resp.status_code == 200
    out = client.get("/retrieve", params={
        "tenant_id": "t1", "user_id": "u1", "agent_id": "a1", "query": "smoke"})
    assert out.status_code == 200
    assert "API smoke note" in out.json()["episodic"]
