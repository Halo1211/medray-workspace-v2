from fastapi.testclient import TestClient

from app.main import app


def test_reference_catalog_has_sources_and_gaps():
    res = TestClient(app).get("/api/references")

    assert res.status_code == 200
    data = res.json()
    assert data["version"]
    assert len(data["sources"]) >= 5
    assert any(source["name"] == "MedRAX" for source in data["sources"])
    assert any(source["name"] == "FDA Clinical Decision Support Software guidance" for source in data["sources"])
    assert any(pattern["pattern"] == "Reviewable result cards" for pattern in data["inspiration_patterns"])
    assert any(gap["area"] == "Clinical validity" for gap in data["maturity_gaps"])
