# tests/test_inference.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from game import app
import json

client = TestClient(app)

@pytest.fixture
def mock_registry():
    """AIレジストリのモック生成"""
    reg = MagicMock()
    adapter = MagicMock()
    adapter.infer.return_value = {
        "move": "5p",
        "score": 0.84,
        "metadata": {"shanten": 1, "safety": 0.72}
    }
    reg.get_adapter.return_value = adapter
    reg.engine_configs = {
        "rlcard": {"repo_id": "dummy", "expected_files": ["model.onnx"]}
    }
    return reg

def test_suggest_move_endpoint(mock_registry):
    with patch("server.endpoints.inference.get_registry", return_value=mock_registry):
        response = client.post("/api/v1/inference/suggest", json={
            "state": {
                "hand": ["1m","2m","3m","5p","5p","7s","8s","9s","2z","3z","4z","5z","6z"],
                "context": {"round": "東2", "score_diff": -5000, "is_dealer": False, "turn_count": 8}
            },
            "engine": "rlcard"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # レスポンス構造検証
        assert "recommended_move" in data
        assert data["recommended_move"] == "5p"
        assert "explanation" in data
        assert data["explanation"]["technical_factors"][0]["label"] == "向聴数前進"
        assert data["confidence"] >= 0.0

def test_model_status_endpoint(mock_registry):
    with patch("server.endpoints.inference.get_registry", return_value=mock_registry):
        response = client.get("/api/v1/inference/models/status")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
