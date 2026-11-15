import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from aperag.evaluation.baseline import (
    BaselineRunner,
    BotClient,
    citation_contexts,
    load_cases,
    retrieval_scores,
    summarize,
    validate_langfuse_destination,
    verify_experiment,
    verify_report,
)
from aperag.evaluation.run import EvaluationRunner


def test_explicit_selfhost_target_cannot_be_overridden_by_ambient_cloud(monkeypatch):
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")
    with pytest.raises(ValueError, match="must match"):
        validate_langfuse_destination({"langfuse_base_url": "http://localhost:3300"})
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://localhost:3300/")
    assert validate_langfuse_destination({"langfuse_base_url": "http://localhost:3300"}) == "http://localhost:3300"


@pytest.mark.parametrize("serialized", [False, True])
def test_readback_accepts_structured_or_json_text_outputs(serialized):
    client = MagicMock()
    output = {"case_id": "a"}
    item = SimpleNamespace(output=json.dumps(output) if serialized else output,
                           scores=[SimpleNamespace(name="quality", value=.75)])
    client.api.experiments.list_items.return_value = SimpleNamespace(
        data=[item], meta=SimpleNamespace(cursor=None))
    receipt = verify_experiment(client, "run", {"a": {"quality": .75}},
                                datetime.now(timezone.utc), timeout_seconds=0)
    assert receipt["case_count"] == receipt["score_count"] == 1


def test_readback_rejects_matching_score_names_with_wrong_values():
    client = MagicMock()
    item = SimpleNamespace(output='{"case_id":"a"}',
                           scores=[SimpleNamespace(name="quality", value=0)])
    client.api.experiments.list_items.return_value = SimpleNamespace(
        data=[item], meta=SimpleNamespace(cursor=None))
    with pytest.raises(TimeoutError):
        verify_experiment(client, "run", {"a": {"quality": .75}},
                          datetime.now(timezone.utc), timeout_seconds=0)


def test_report_recovery_preserves_generation_provenance_without_model_calls(tmp_path, monkeypatch):
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://localhost:3300")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "public")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "secret")
    path = tmp_path / "baseline.json"
    original = {"expected_cases": 1, "executed_cases": 1,
        "experiment_url": "http://localhost:3300/project/p/experiments/results?baseline=run",
        "run_name": "baseline-20261028T001007366896Z", "publication_error": "TimeoutError",
        "metadata": {"evaluator_revision": "original-generation"},
        "results": [{"case_id": "a", "scores": {"quality": .75}}]}
    path.write_text(json.dumps(original), encoding="utf-8")
    with patch("aperag.evaluation.baseline.Langfuse"), \
         patch("aperag.evaluation.baseline.verify_experiment", return_value={"case_count": 1, "score_count": 1}), \
         patch("aperag.evaluation.baseline.subprocess.check_output", return_value="new-verifier"), \
         patch("aperag.evaluation.baseline.BaselineRunner", side_effect=AssertionError("no judge setup")):
        result = verify_report(path)
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted == result
    assert result["metadata"]["evaluator_revision"] == "original-generation"
    assert result["publication_error_history"] == ["TimeoutError"]
    assert result["publication_verification"]["verifier_revision"] == "new-verifier"
    assert result["publication_verified"] is True


def test_document_metrics_deduplicate_and_distinguish_recall_from_hit():
    items = [{"metadata": {"document_id": doc}} for doc in ["noise", "a", "a", "b"]]
    scores = retrieval_scores(items, ["a", "b", "c", "d"])
    assert scores["probe_document_recall_at_1"] == 0
    assert scores["probe_document_recall_at_3"] == .5
    assert scores["probe_document_recall_at_5"] == .5
    assert scores["probe_document_mrr_at_5"] == .5


def test_unlabelled_retrieval_is_unknown_and_missing_identity_fails():
    assert retrieval_scores([], []) == {}
    with pytest.raises(ValueError, match="document_id"):
        retrieval_scores([{"source": "some title"}], ["a"])
    assert retrieval_scores([], ["a"])["probe_document_mrr_at_5"] == 0


def test_titles_and_citation_metadata_are_not_evidence_text():
    assert citation_contexts([{"title": "a", "metadata": {"document_id": "a"}}]) == []
    assert citation_contexts([{"content": "real evidence"}]) == [{"text": "real evidence"}]


def test_existing_context_preparation_accepts_references_without_text():
    runner = EvaluationRunner.__new__(EvaluationRunner)
    data = runner._prepare_ragas_dataset([{
        "question": "q", "response": "a", "ground_truth": "a", "context": [{"title": "doc"}]
    }])
    assert len(data) == 1
    assert data[0]["contexts"] == [""]


def test_llm_context_metrics_do_not_require_embeddings():
    runner = EvaluationRunner.__new__(EvaluationRunner)
    runner.embeddings_for_eval = None
    assert len(runner._get_metrics(["context_recall", "context_precision", "factual_correctness"])) == 3


def test_dataset_preserves_repeated_questions_but_rejects_duplicate_ids(tmp_path):
    case = {"id": "a", "question": "same", "answer": "a", "scenario": "faq", "expected_action": "answer"}
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([case, {**case, "id": "b"}]), encoding="utf-8")
    assert len(load_cases(path)) == 2
    path.write_text(json.dumps([case, case]), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        load_cases(path)


def test_failures_stay_in_denominator_and_task_success_is_not_inferred():
    result = summarize([
        {"output": {"error": None, "response_time": 1}, "scores": {"request_success": 1}},
        {"output": {"error": "TimeoutError", "response_time": 5}, "scores": {"request_success": 0}},
    ])
    assert result["total"] == 2
    assert result["request_failure_rate"] == .5
    assert result["response_p95_seconds"] == 5
    assert result["task_pass_rate"] is None


def test_expected_clarification_is_not_sent_to_answer_correctness_judge():
    runner = BaselineRunner.__new__(BaselineRunner)
    runner.config = {"metrics": ["factual_correctness"]}
    runner._run_ragas_evaluation = MagicMock(side_effect=AssertionError("must not evaluate"))
    scores, notes = runner.evaluate_case({"expected_action": "clarify"}, {"error": None, "response": "which error?"})
    assert scores == {"request_success": 1}
    assert "human review" in notes[0]


@pytest.mark.parametrize("events,expected_error", [
    ([{"type": "message", "data": "answer"}, {"type": "stop", "data": [{"text": "source"}]}], None),
    ([{"type": "error", "data": "sensitive details"}], "RuntimeError"),
    ([{"type": "stop"}], "RuntimeError"),
    ([TimeoutError()], "TimeoutError"),
])
def test_real_bot_protocol_and_failures(events, expected_error):
    client = BotClient({"base_url": "http://localhost:8000/api/v1", "session_cookie": "secret"})
    client.http = MagicMock()
    client.http.post.return_value.json.return_value = {"id": "new-chat"}
    socket = MagicMock()
    socket.recv.side_effect = [json.dumps(event) if isinstance(event, dict) else event for event in events]
    with patch("aperag.evaluation.baseline.connect") as connection:
        connection.return_value.__enter__.return_value = socket
        result = client.run("bot", {"question": "q"})
        assert connection.call_args.kwargs["additional_headers"] == {"Cookie": "session=secret"}
    assert result["error"] == expected_error
    assert "sensitive" not in json.dumps(result)
    if expected_error is None:
        assert result["response"] == "answer"
        assert result["context"] == [{"text": "source"}]
        assert "probe_document_recall_at_5" not in result


def test_ragas_nan_is_unavailable_and_repeated_case_alignment_is_local():
    runner = BaselineRunner.__new__(BaselineRunner)
    runner.config = {"metrics": ["factual_correctness", "faithfulness"]}

    async def scores(*args):
        return [{"factual_correctness(mode=f1)": .75, "faithfulness": float("nan")}]

    runner._run_ragas_evaluation = scores
    result, notes = runner.evaluate_case({"question": "q", "answer": "a", "expected_action": "answer"},
        {"error": None, "response": "a", "context": [{"text": "a"}]})
    assert result["ragas_factual_correctness"] == .75
    assert "ragas_cited_faithfulness" not in result
    assert any("unavailable" in note for note in notes)
