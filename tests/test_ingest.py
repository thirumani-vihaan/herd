"""Tests for the Ingest API."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

@pytest.fixture(autouse=True)
def mock_container():
    with patch("app.api.ingest.build_container") as mock_bc:
        mock_cont = AsyncMock()
        mock_cont.store.init = AsyncMock()
        mock_cont.fetcher.aclose = AsyncMock()
        mock_bc.return_value = mock_cont
        
        with patch("app.api.ingest.get_institution"):
            yield mock_cont

@pytest.fixture
def client():
    from app.api.ingest import app
    with TestClient(app) as c:
        yield c

def test_ingest_idempotency(client):
    data = {
        "text": "TCS placement drive 2026",
        "reporter_hash": "rep_123",
        "is_forwarded": False,
        "is_frequently_forwarded": False,
    }
    
    with patch("app.api.ingest.process_pipeline") as mock_pipeline:
        response1 = client.post("/ingest", data=data)
        assert response1.status_code == 200
        res1 = response1.json()
        assert res1["status"] == "accepted"
        assert "tracking_id" in res1
        
        # Second call should be duplicate
        response2 = client.post("/ingest", data=data)
        assert response2.status_code == 200
        res2 = response2.json()
        assert res2["status"] == "duplicate_received"
        assert res1["tracking_id"] == res2["tracking_id"]
        
        mock_pipeline.assert_called_once()
