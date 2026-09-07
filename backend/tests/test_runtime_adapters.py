import json

from app.models.schemas import RuntimeConfig
from app.runtime.adapters import chat_response, endpoint_is_local


def test_demo_chat_counts_reviewed_case_annotations_before_analysis_copy():
    reply = chat_response(
        "berapa anotasi?",
        [],
        RuntimeConfig(primary_backend="demo"),
        {
            "annotations": [{"id": "reviewed-1"}, {"id": "reviewed-2"}],
            "analysis": {"annotations": [{"id": "stale-analysis"}]},
        },
    )

    assert "Ada 2 anotasi" in reply["content"]


def test_demo_chat_ignores_malformed_annotation_collections():
    reply = chat_response(
        "berapa anotasi?",
        [],
        RuntimeConfig(primary_backend="demo"),
        {
            "annotations": "not-a-list",
            "analysis": {"annotations": "not-a-list"},
        },
    )

    assert "Ada 0 anotasi" in reply["content"]


def test_chat_sanitizes_malformed_analysis_context(monkeypatch):
    captured = {}

    def fake_chat(messages, model, base_url):
        captured["content"] = messages[-1]["content"]
        return "ok"

    import app.runtime.adapters as adapters

    monkeypatch.setattr(adapters, "ollama_chat", fake_chat)
    reply = chat_response(
        "ringkas",
        [],
        RuntimeConfig(primary_backend="ollama", chat_model="local-model"),
        {
            "analysis": {
                "findings": "not-a-list",
                "annotations": "not-a-list",
                "result_cards": "not-a-list",
                "warnings": "not-a-list",
                "model_trace": "not-a-list",
            },
        },
    )

    context_json = captured["content"].split("Context kasus terstruktur: ", 1)[1].split("\n\nMetadata/runtime", 1)[0]
    focused_context = json.loads(context_json)
    assert reply["backend"] == "ollama"
    assert focused_context["analysis_findings"] == []
    assert focused_context["annotations"] == []
    assert focused_context["result_cards"] == []
    assert focused_context["warnings"] == []
    assert focused_context["model_trace"] == []


def test_cloud_endpoint_is_blocked_until_explicitly_allowed(monkeypatch):
    called = False

    def fake_chat(*_args, **_kwargs):
        nonlocal called
        called = True
        return "should not be sent"

    import app.runtime.adapters as adapters

    monkeypatch.setattr(adapters, "openai_compatible_chat", fake_chat)
    reply = chat_response(
        "ringkas",
        [],
        RuntimeConfig(
            primary_backend="openai-compatible",
            openai_base_url="https://remote.example/v1",
            chat_model="selected-cloud-model",
            allow_cloud=False,
        ),
        {"metadata": {"PatientID": "private-id"}},
    )

    assert called is False
    assert reply["fallback"] is True
    assert "Cloud endpoint blocked" in reply["content"]
    assert endpoint_is_local("http://127.0.0.1:8000/v1") is True
    assert endpoint_is_local("http://[::1]:8000/v1") is True
    assert endpoint_is_local("https://remote.example/v1") is False


def test_demo_chat_and_provider_prompt_follow_requested_language(monkeypatch):
    english = chat_response("How many annotations?", [], RuntimeConfig(primary_backend="demo"), {"annotations": []}, language="en")
    indonesian = chat_response("Berapa anotasi?", [], RuntimeConfig(primary_backend="demo"), {"annotations": []}, language="id")
    assert "There are 0 annotations" in english["content"]
    assert "Ada 0 anotasi" in indonesian["content"]

    captured = {}
    import app.runtime.adapters as adapters
    monkeypatch.setattr(adapters, "ollama_chat", lambda messages, *_args: captured.setdefault("prompt", messages[-1]["content"]) or "ok")
    chat_response("Summarize", [], RuntimeConfig(primary_backend="ollama", chat_model="local"), {"analysis": {}}, language="en")
    assert "Structured case context" in captured["prompt"]
    assert "Respond entirely in English" in captured["prompt"]


def test_advanced_generation_controls_reach_provider(monkeypatch):
    captured = {}
    import app.runtime.adapters as adapters

    def fake_chat(messages, model, base_url, *, temperature, top_p, seed, max_output_tokens, timeout, max_retries):
        captured.update(temperature=temperature, top_p=top_p, seed=seed, max_output_tokens=max_output_tokens, timeout=timeout, max_retries=max_retries)
        return "ok"

    monkeypatch.setattr(adapters, "ollama_chat", fake_chat)
    reply = chat_response(
        "Summarize",
        [],
        RuntimeConfig(primary_backend="ollama", chat_model="local", temperature=0.4, top_p=0.8, seed=7, max_output_tokens=4096, request_timeout_seconds=240, max_retries=3),
        {"analysis": {}},
        language="en",
    )
    assert reply["fallback"] is False
    assert captured == {"temperature": 0.4, "top_p": 0.8, "seed": 7, "max_output_tokens": 4096, "timeout": 240, "max_retries": 3}
