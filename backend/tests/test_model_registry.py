from fastapi.testclient import TestClient

from app.main import app
from app.model_registry.cards import get_model_card


def test_demo_model_card_available():
    card = get_model_card("demo-classifier")

    assert card["clinical_status"] == "placeholder"
    assert card["requires_opt_in_cloud"] is False


def test_model_cards_endpoint():
    res = TestClient(app).get("/api/model-cards")

    assert res.status_code == 200
    assert any(card["id"] == "demo-report-generator" for card in res.json())
