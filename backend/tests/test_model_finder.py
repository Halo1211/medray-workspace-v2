import pytest

from app.model_finder import providers
from app.config import get_settings
from app.audit.bundle import build_audit_bundle
from app.model_registry.cards import get_model_card
from app.model_finder.providers import (
    estimate_vram,
    infer_task,
    list_local_model_artifacts,
    list_ollama_models,
    maturity_score,
    model_card_readiness,
    model_detail,
    runtime_hardware_plan,
    runtime_local_model_gate_issues,
    save_local_model_card,
    search_all_sources,
    search_github,
    search_hugging_face,
    validate_local_model_import,
)
import urllib.error
from types import SimpleNamespace


def test_model_task_parser():
    assert infer_task("chest xray segmentation sam") == "segmentation"
    assert infer_task("chexpert densenet classifier") == "classification"


def test_vram_parser():
    assert estimate_vram("medgemma 4b q4") == "4GB-6GB"


def test_model_scoring():
    assert maturity_score("chexpert chest xray classifier model card", "apache-2.0") >= 60


def test_runtime_hardware_plan_maps_runtime_slots():
    plan = runtime_hardware_plan()
    slots = {item["slot"] for item in plan["runtime_slots"]}
    labels = {item["label"] for item in plan["runtime_slots"]}

    assert plan["profile"]["tier"] in {"cpu", "low", "mid", "high"}
    assert {"classification_model", "segmentation_model", "report_model"} <= slots
    assert labels == {"X-ray analysis", "X-ray localization", "X-ray report & chat"}
    assert all(item["source"] == "all" for item in plan["runtime_slots"])
    assert plan["download_help"]["not_runtime"]


def test_search_all_sources_does_not_inject_starter_fallback(monkeypatch):
    monkeypatch.setattr(providers, "search_hugging_face", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("hf offline")))
    monkeypatch.setattr(providers, "search_github", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(providers, "list_ollama_models", lambda: {"models": [], "service": False})

    payload = search_all_sources("chest xray classifier", 8, 1)

    assert payload["source"] == "All sources"
    assert payload["results"] == []
    assert any("Hugging Face" in error for error in payload["errors"])


def test_search_all_sources_skips_ollama_for_non_text_slots(monkeypatch):
    monkeypatch.setattr(providers, "search_hugging_face", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(providers, "search_github", lambda *_args, **_kwargs: [])

    def fail_ollama():
        raise AssertionError("Ollama should not be queried for segmentation search")

    monkeypatch.setattr(providers, "list_ollama_models", fail_ollama)

    payload = search_all_sources("medical image segmentation chest xray sam huggingface", 8, 1)

    assert payload["results"] == []
    assert not payload["errors"]
    assert "xray segmentation" in payload["queries_used"]


def test_model_card_readiness_flags_missing_review_facts():
    readiness = model_card_readiness({"name": "toy demo", "license": "unknown", "task_type": "unknown", "tags": []})

    assert readiness["score"] < 50
    assert "License declared" in readiness["missing"]
    assert readiness["action_required"].startswith("Add/review")


def test_model_card_readiness_ignores_non_array_tags():
    readiness = model_card_readiness({"name": "cxr model", "license": "mit", "task_type": "classification", "tags": "cxr"})

    assert readiness["license"] == "mit"
    assert isinstance(readiness["checks"], list)


def test_external_searches_tolerate_malformed_payloads(monkeypatch):
    monkeypatch.setattr(providers, "_get_json", lambda url, timeout=20: {"error": "bad shape"})
    assert search_hugging_face("chest xray") == []
    assert search_github("chest xray") == []


def test_ollama_listing_tolerates_malformed_tags(monkeypatch):
    monkeypatch.setattr(providers, "ollama_tags", lambda: {"models": "not-a-list"})
    monkeypatch.setattr(providers, "ollama_installed", lambda: True)

    payload = list_ollama_models()

    assert payload["service"] is True
    assert payload["models"] == []


def test_starter_model_detail_has_readiness_gate():
    detail = model_detail("starter", "starter:torchxrayvision")

    assert detail["id"] == "starter:torchxrayvision"
    assert detail["card_readiness"]["action_required"]
    assert "analysis" in detail["card_readiness"]["action_required"]


def test_model_detail_rate_limit_degrades_to_review_panel(monkeypatch):
    def rate_limited(*_args, **_kwargs):
        raise urllib.error.HTTPError("https://huggingface.co/api/models/test/model", 403, "rate limit exceeded", {}, None)

    monkeypatch.setattr(providers, "_get_json", rate_limited)

    detail = model_detail("hf", "test/model")

    assert detail["metadata_unavailable"] is True
    assert detail["metadata_error"] == "rate limit exceeded"
    assert detail["card_readiness"]["action_required"]


def test_huggingface_token_status_hides_token():
    token_path = providers._huggingface_token_path()
    original = token_path.read_text(encoding="utf-8") if token_path.exists() else None
    try:
        status = providers.save_huggingface_token("hf_test_not_real")

        assert status["configured"] is True
        assert "hf_test_not_real" not in str(status)
        assert providers.load_huggingface_token() == "hf_test_not_real"

        cleared = providers.clear_huggingface_token()
        assert cleared["configured"] is False
    finally:
        if original is not None:
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(original, encoding="utf-8")
        elif token_path.exists():
            token_path.unlink()


def test_github_token_status_hides_token():
    token_path = providers._github_token_path()
    original = token_path.read_text(encoding="utf-8") if token_path.exists() else None
    try:
        status = providers.save_github_token("github_test_not_real")

        assert status["configured"] is True
        assert "github_test_not_real" not in str(status)
        assert providers.load_github_token() == "github_test_not_real"

        headers = providers.request_headers("https://api.github.com/search/repositories?q=xray")
        assert headers["Authorization"] == "Bearer github_test_not_real"

        cleared = providers.clear_github_token()
        assert cleared["configured"] is False
    finally:
        if original is not None:
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(original, encoding="utf-8")
        elif token_path.exists():
            token_path.unlink()


def test_tokens_are_not_sent_to_lookalike_domains(monkeypatch):
    monkeypatch.setattr(providers, "load_huggingface_token", lambda: "hf-secret")
    monkeypatch.setattr(providers, "load_github_token", lambda: "gh-secret")

    assert "Authorization" not in providers.request_headers("https://huggingface.co.attacker.example/model")
    assert "Authorization" not in providers.request_headers("https://api.github.com.attacker.example/repos")
    assert providers.request_headers("https://huggingface.co/org/model")["Authorization"] == "Bearer hf-secret"
    assert providers.request_headers("https://api.github.com/repos/org/model")["Authorization"] == "Bearer gh-secret"


def test_download_manager_allocates_unique_targets(tmp_path, monkeypatch):
    monkeypatch.setattr(providers, "get_settings", lambda: SimpleNamespace(models_dir=tmp_path))
    manager = providers.DownloadManager()

    first = manager._target_path("https://example.test/model.gguf", "model.gguf", "11111111-job")
    second = manager._target_path("https://example.test/model.gguf", "model.gguf", "22222222-job")

    assert first != second
    assert first.with_suffix(first.suffix + ".part") != second.with_suffix(second.suffix + ".part")


def test_manual_download_rejects_local_destinations(monkeypatch):
    with pytest.raises(ValueError, match="loopback|private"):
        providers._validate_manual_download_url("http://127.0.0.1:8765/model.gguf")


def test_manual_download_accepts_public_ip_literal(monkeypatch):
    monkeypatch.setattr(providers.socket, "getaddrinfo", lambda *args, **kwargs: [(None, None, None, None, ("93.184.216.34", 80))])
    providers._validate_manual_download_url("https://example.test/model.gguf")


def test_local_artifact_requires_reviewed_model_card():
    settings = get_settings()
    artifact = settings.models_dir / "pytest-local-model"
    artifact.mkdir(parents=True, exist_ok=True)
    (artifact / "config.json").write_text("{}", encoding="utf-8")
    card_path = providers._local_card_path(providers._local_artifact_id(artifact))
    if card_path.exists():
        card_path.unlink()
    try:
        item = next(model for model in list_local_model_artifacts() if model["name"] == artifact.name)
        assert item["state"] == "review_needed"
        assert item["runtime_eligible"] is False

        card = save_local_model_card(
            {
                "artifact_path": str(artifact),
                "intended_use": "Local research signal only.",
                "task": "classification",
                "license": "local-test",
                "dataset_provenance": "pytest fixture",
                "hardware": "CPU",
                "limitations": "Not clinically validated.",
                "contraindicated_use": "No clinical triage.",
                "validation_status": "not validated",
                "human_reviewed": True,
            }
        )
        assert card["runtime_eligible"] is True
        assert card["card_path"].endswith(".model-card.json")
        reviewed = next(model for model in list_local_model_artifacts() if model["name"] == artifact.name)
        assert reviewed["state"] == "reviewed"
        assert reviewed["card_path"].endswith(".model-card.json")
    finally:
        for child in artifact.glob("*"):
            child.unlink()
        if artifact.exists():
            artifact.rmdir()
        if card_path.exists():
            card_path.unlink()


def test_import_folder_validation_reports_readiness_and_warnings():
    settings = get_settings()
    artifact = settings.models_dir / "pytest-import-model"
    artifact.mkdir(parents=True, exist_ok=True)
    (artifact / "model.safetensors").write_text("x", encoding="utf-8")
    card_path = providers._local_card_path(providers._local_artifact_id(artifact))
    if card_path.exists():
        card_path.unlink()
    try:
        validation = validate_local_model_import(str(artifact))

        assert validation["safe_path"] is True
        assert validation["likely_model"] is True
        assert validation["readiness"] == "ready_for_model_card_review"
        assert validation["model_card_status"] == "missing"
        assert validation["task_slot"] == "classification_model"
        assert any("README" in warning for warning in validation["warnings"])
        assert any("license" in warning.lower() for warning in validation["warnings"])
    finally:
        for child in artifact.glob("*"):
            child.unlink()
        if artifact.exists():
            artifact.rmdir()
        if card_path.exists():
            card_path.unlink()


def test_runtime_gate_blocks_unreviewed_local_artifact_path():
    settings = get_settings()
    artifact = settings.models_dir / "pytest-runtime-model"
    artifact.mkdir(parents=True, exist_ok=True)
    (artifact / "model.safetensors").write_text("x", encoding="utf-8")
    card_path = providers._local_card_path(providers._local_artifact_id(artifact))
    if card_path.exists():
        card_path.unlink()
    try:
        payload = {"classification_model": str(artifact)}
        assert runtime_local_model_gate_issues(payload)

        save_local_model_card(
            {
                "artifact_path": str(artifact),
                "intended_use": "Local research signal only.",
                "task": "classification",
                "license": "local-test",
                "dataset_provenance": "pytest fixture",
                "limitations": "Not clinically validated.",
                "validation_status": "not validated",
                "human_reviewed": True,
            }
        )
        assert runtime_local_model_gate_issues(payload) == []
    finally:
        for child in artifact.glob("*"):
            child.unlink()
        if artifact.exists():
            artifact.rmdir()
        if card_path.exists():
            card_path.unlink()


def test_structured_validation_evidence_binds_exact_weights_and_reports_status():
    settings = get_settings()
    artifact = settings.models_dir / "pytest-structured-evidence-model"
    artifact.mkdir(parents=True, exist_ok=True)
    weights = artifact / "fracture.pt"
    weights.write_bytes(b"reviewed-test-weights")
    card_path = providers._local_card_path(providers._local_artifact_id(artifact))
    if card_path.exists():
        card_path.unlink()
    try:
        incomplete = save_local_model_card(
            {
                "artifact_path": str(artifact),
                "intended_use": "Local MSK research localization signal only.",
                "task": "MSK fracture localization",
                "license": "local-test",
                "dataset_provenance": "pytest held-out fixture",
                "limitations": "Not clinical performance.",
                "human_reviewed": True,
            }
        )
        assert incomplete["runtime_eligible"] is True
        assert incomplete["validation_evidence_status"] == "structured_evidence_incomplete"
        assert incomplete["confidence_posture"] == "conservative_unvalidated"

        complete = save_local_model_card(
            {
                **incomplete,
                "artifact_path": str(artifact),
                "human_reviewed": True,
                "validation_evidence": {
                    "protocol_id": "MSK-BOX-001",
                    "dataset_name": "Local held-out fracture set",
                    "held_out_split": "test-v1",
                    "case_count": 12,
                    "label_count": 18,
                    "metric_summary": {"box_hit_rate": 0.75, "mean_best_iou": 0.61},
                    "false_alert_burden": {"false_alert_count": 2, "false_alerts_per_case": 0.167},
                    "known_failures": ["Oblique views underrepresented"],
                    "subgroup_coverage": {"anatomy": ["wrist"], "views": ["AP"], "age_groups": ["adult"]},
                    "reviewer": "pytest reviewer",
                    "review_date": "2026-07-12",
                    "weights_filename": "fracture.pt",
                },
            }
        )
        assert complete["validation_evidence_status"] == "locally_validated_for_protocol"
        assert complete["confidence_posture"] == "protocol_bounded_research_evidence"
        assert complete["validation_evidence"]["artifact_hash"] == providers.hashlib.sha256(b"reviewed-test-weights").hexdigest()
        listed = next(model for model in list_local_model_artifacts() if model["name"] == artifact.name)
        assert listed["human_review_status"] == "human_reviewed"
        assert listed["validation_evidence_status"] == "locally_validated_for_protocol"
        registry_card = get_model_card(complete["artifact_id"])
        assert registry_card["validation_evidence"]["protocol_id"] == "MSK-BOX-001"
        audit = build_audit_bundle({"case_id": "evidence-audit", "analysis": {"model_trace": [{"model": complete["artifact_id"]}]}})
        assert audit["validation_evidence_used"][0]["validation_evidence_status"] == "locally_validated_for_protocol"
        assert audit["validation_evidence_used"][0]["validation_evidence"]["weights_filename"] == "fracture.pt"
    finally:
        for child in artifact.glob("*"):
            child.unlink()
        if artifact.exists():
            artifact.rmdir()
        if card_path.exists():
            card_path.unlink()
