import pytest
from fastapi.testclient import TestClient
from server.app import app

client = TestClient(app)

def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "game": "mahjong-ai"}

def test_index():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

@pytest.mark.asyncio
async def test_websocket_ui():
    with client.websocket_connect("/ws_ui") as websocket:
        # Initial connect should send state_sync
        data = websocket.receive_json()
        assert data["type"] in ["state_sync", "game_state"]
        assert "data" in data or "state" in data

        # send a dummy message to test interaction
        # human_seat is -1 so it will be ignored but shouldn't crash
        websocket.send_json({"action": "dummy"})
