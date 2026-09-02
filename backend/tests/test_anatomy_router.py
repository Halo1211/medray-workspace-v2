from fastapi.testclient import TestClient

from app.anatomy.router import anatomy_profiles, resolve_profile_model, route_study
from app.main import app


def test_dicom_body_part_has_priority_and_preserves_view_and_laterality():
    route = route_study(
        {"BodyPartExamined": "WRIST", "ViewPosition": "PA", "Laterality": "R"},
        "chest.png",
        "review abdomen",
    )

    assert route["profile_id"] == "msk"
    assert route["anatomy"] == "wrist"
    assert route["laterality"] == "right"
    assert route["view"] == "PA"
    assert route["source"] == "dicom_body_part"
    assert route["confidence"] == 0.99


def test_specific_spine_term_wins_over_generic_xray_context():
    route = route_study({}, "thoracic_spine_lateral_xray.png")

    assert route["profile_id"] == "spine"
    assert route["anatomy"] == "thoracic spine"
    assert route["view"] == "LATERAL"
    assert route["model_slot"] == "spine_xray_model"


def test_unknown_anatomy_blocks_general_model_until_confirmed():
    route = route_study({}, "study-001.png")
    resolved = resolve_profile_model(route, {"general_xray_model": "some-vlm", "vision_language_model": "common-vlm"})

    assert resolved["profile_id"] == "general"
    assert resolved["selected_model"] == "disabled"
    assert resolved["support_status"] == "routing_required"
    assert any("not sent" in warning for warning in resolved["warnings"])


def test_profile_model_can_inherit_common_vlm():
    route = route_study({"BodyPartExamined": "ABDOMEN"}, "study.png")
    resolved = resolve_profile_model(route, {"abdomen_xray_model": "inherit", "vision_language_model": "local-vision"})

    assert resolved["profile_id"] == "abdomen"
    assert resolved["selected_model"] == "local-vision"
    assert resolved["support_status"] == "configured_unvalidated"


def test_profile_model_ignores_malformed_route_warnings():
    route = route_study({"BodyPartExamined": "ABDOMEN"}, "study.png")
    route["warnings"] = "not-a-list"
    resolved = resolve_profile_model(route, {"abdomen_xray_model": "disabled"})

    assert resolved["warnings"] == []


def test_reviewer_override_replaces_automatic_route_and_is_auditable():
    route = route_study({"BodyPartExamined": "CHEST"}, "chest.png", profile_override="spine")

    assert route["profile_id"] == "spine"
    assert route["source"] == "reviewer_override"
    assert route["confidence"] == 1.0
    assert route["model_slot"] == "spine_xray_model"


def test_anatomy_profiles_api_exposes_all_initial_xray_groups():
    response = TestClient(app).get("/api/anatomy/profiles")

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert ids == {"chest", "msk", "abdomen", "spine", "skull_facial", "general"}
    assert len(anatomy_profiles()) == 6


def test_runtime_api_includes_anatomy_specific_model_slots():
    response = TestClient(app).get("/api/runtime")

    assert response.status_code == 200
    runtime = response.json()
    assert runtime["chest_xray_model"] == "inherit"
    assert runtime["msk_xray_model"] == "inherit"
    assert runtime["general_xray_model"] == "disabled"
