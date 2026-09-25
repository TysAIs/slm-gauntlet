"""Integration: full CLI run against a mock endpoint producing known-good answers."""

import json

import httpx

from gauntlet.cli import main


def _mock_handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    user_text = " ".join(m["content"] or "" for m in body["messages"] if m.get("role") == "user")

    # produce correct answers for a slice of tasks; wrong for the rest (deterministic)
    answers = {
        "capital of France": "The capital of France is Paris.",
        "42": "42",
        "GAUNTLET_OK": "GAUNTLET_OK",
        "NOT_FOUND": "NOT_FOUND",
    }
    content = "I cannot answer this specific question with certainty."
    for key, ans in answers.items():
        if key in user_text:
            content = ans
            break
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 10},
        },
        request=request,
    )


def test_cli_run_writes_results_and_scores(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # results/ lands in tmp
    transport = httpx.MockTransport(_mock_handler)
    # patch client creation to inject transport
    import gauntlet.client as client_mod

    orig_init = client_mod.GauntletClient.__init__

    def patched(self, base_url, model, transport=transport, timeout=600.0, max_retries=3, api_key=None):
        orig_init(self, base_url, model, transport=transport, timeout=timeout, max_retries=max_retries, api_key=api_key)

    monkeypatch.setattr(client_mod.GauntletClient, "__init__", patched)

    rc = main([
        "run", "--endpoint", "http://mock/v1", "--model", "mock-model",
        "--suite", "tooluse", "--concurrency", "4",
    ])
    assert rc == 0

    files = list((tmp_path / "results").glob("*.json"))
    assert files, "results file must be written"
    data = json.loads(files[0].read_text())
    assert data["meta"]["model"] == "mock-model"
    assert len(data["results"]) > 0
    # Paris + GAUNTLET_OK tasks must pass; others fail
    passed_ids = {r["task_id"] for r in data["results"] if r["pass1"] > 0}
    assert "tool_irrelevant_refusal" in passed_ids
    assert "tool_file_write_read" in passed_ids
    assert "tool_single_call" not in passed_ids


def test_report_generates_table(tmp_path, monkeypatch):
    results = [
        {"task_id": "a", "suite": "tooluse", "pass1": 1.0, "pass_k": 1.0, "attempts": [{"terminated": "completed"}]},
        {"task_id": "b", "suite": "coding", "pass1": 0.0, "pass_k": 0.0, "attempts": [{"terminated": "looped"}]},
    ]
    d = tmp_path / "results"
    d.mkdir()
    (d / "model_test_20260925.json").write_text(
        json.dumps({"meta": {"model": "test/model"}, "results": results})
    )
    from gauntlet.report import generate_leaderboard

    table = generate_leaderboard(d)
    assert "test/model" in table
    # tooluse 1.0 * 0.4 + coding 0.0 * 0.1, renormalized over 0.5 total weight = 0.8
    assert "0.8" in table
