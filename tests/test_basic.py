import pytest
from unittest.mock import MagicMock


def test_semantic_aggregator_basic():
    """Test semantic aggregator utility joins text correctly"""
    from app.utils.semantic_aggregator import SemanticSegment
    
    segment = SemanticSegment()
    segment.add_word("Hello", 0.0, 0.5)
    segment.add_word("world", 0.6, 1.0)
    segment.add_word("test", 1.1, 1.5)
    
    result = segment.get_text()
    
    assert result == "Hello world test"
    assert segment.start_time == 0.0
    assert segment.end_time == 1.5
    assert segment.get_length() == 16


def test_health_endpoint():
    """Test that FastAPI app health endpoint responds"""
    from fastapi.testclient import TestClient
    from app.main import app
    
    client = TestClient(app)
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
