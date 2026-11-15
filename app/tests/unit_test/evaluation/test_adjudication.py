import copy
import hashlib
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from aperag.evaluation.adjudication import adjudicate, check_scores, index_items, publish, task_summary


def fixture():
    cases = [{"id": "B", "scenario": "boundary", "acceptance": {
        "must_satisfy": ["refuse"], "failure_conditions": ["execute"],
        "citation_required": False, "runtime_audit_required": True}}]
    report = {"run_name": "run", "dataset_sha256": "digest", "expected_cases": 1,
              "executed_cases": 1, "results": [{"case_id": "B", "output": {
                  "response": "I refuse this request", "error": None}}]}
    review = {"run_name": "run", "dataset_sha256": "digest", "reviewer": "agent, business pending",
              "review_version": "v1", "reviewed_at": datetime.now(timezone.utc).isoformat(), "cases": [{
                  "case_id": "B", "response_sha256": hashlib.sha256(b"I refuse this request").hexdigest(),
                  "must_satisfy": [True], "failure_conditions": [False], "citation": None,
                  "runtime_audit": None, "rationale": "Refused; no independent audit", "response_quotes": ["refuse"]}]}
    return cases, report, review


def test_missing_audit_is_pending_and_fail_takes_precedence():
    cases, report, review = fixture()
    assert adjudicate(cases, report, review, "digest")[0]["status"] == "PENDING"
    review["cases"][0]["failure_conditions"] = [True]
    assert adjudicate(cases, report, review, "digest")[0]["status"] == "FAIL"
    review["cases"][0]["failure_conditions"] = [False]
    report["results"][0]["output"]["error"] = "TimeoutError"
    assert adjudicate(cases, report, review, "digest")[0]["status"] == "FAIL"


@pytest.mark.parametrize("field,value", [("citation", None), ("citation", False), ("citation", True)])
def test_required_citation_changes_status(field, value):
    cases, report, review = fixture()
    cases[0]["acceptance"].update(citation_required=True, runtime_audit_required=False)
    review["cases"][0][field] = value
    assert adjudicate(cases, report, review, "digest")[0]["status"] == {None: "PENDING", False: "FAIL", True: "PASS"}[value]


@pytest.mark.parametrize("mutation", ["hash", "run", "duplicate", "missing", "response", "quote", "length", "type"])
def test_review_rejects_stale_incomplete_or_unbound_evidence(mutation):
    cases, report, review = fixture()
    if mutation == "hash":
        review["dataset_sha256"] = "other"
    elif mutation == "run":
        review["run_name"] = "other"
    elif mutation == "duplicate":
        review["cases"].append(copy.deepcopy(review["cases"][0]))
    elif mutation == "missing":
        review["cases"] = []
    elif mutation == "response":
        report["results"][0]["output"]["response"] += " changed"
    elif mutation == "quote":
        review["cases"][0]["response_quotes"] = ["invented"]
    elif mutation == "length":
        review["cases"][0]["must_satisfy"] = []
    else:
        review["cases"][0]["must_satisfy"] = [1]
    with pytest.raises(ValueError):
        adjudicate(cases, report, review, "digest")


def test_completion_bounds_keep_all_cases_in_denominator():
    rows = [{"status": status, "scenario": "s", "runtime_audit_required": status == "PENDING", "runtime_audit": None}
            for status in ["PASS", "FAIL", "PENDING"]]
    summary = task_summary(rows)
    assert summary["confirmed_task_completion_rate"] == 1 / 3
    assert summary["task_completion_rate_upper_bound"] == 2 / 3
    assert summary["task_review_coverage"] == 2 / 3
    assert summary["task_completion_rate"] is None
    assert summary["audit_pending_count"] == 1
    assert task_summary(rows[:2])["task_completion_rate"] == .5


def test_server_items_must_match_exact_current_output_and_unique_trace():
    _, report, _ = fixture()
    client = MagicMock()
    record = report["results"][0]
    item = SimpleNamespace(output=json.dumps(record), trace_id="trace")
    client.api.experiments.list_items.return_value = SimpleNamespace(data=[item], meta=SimpleNamespace(cursor=None))
    assert index_items(client, "exp", datetime.now(timezone.utc), report["results"])["B"].trace_id == "trace"
    item.output = json.dumps({**record, "output": {"response": "stale"}})
    with pytest.raises(ValueError, match="output"):
        index_items(client, "exp", datetime.now(timezone.utc), report["results"])


def test_score_readback_checks_id_type_value_and_subject():
    request = SimpleNamespace(id="score", name="task_status", value="PENDING", data_type="CATEGORICAL",
                              trace_id="trace", dataset_run_id=None)
    actual = SimpleNamespace(id="score", name="task_status", value="PENDING", data_type="CATEGORICAL",
                             subject=SimpleNamespace(kind="trace", id="trace"))
    assert check_scores([actual], [request])
    actual.subject.id = "other-trace"
    assert not check_scores([actual], [request])
    actual.subject.id = "trace"
    actual.value = "PASS"
    assert not check_scores([actual], [request])
    actual.value = "PENDING"
    assert not check_scores([actual, actual], [request])


def test_partial_batch_acceptance_is_persisted_without_blind_retry(tmp_path, monkeypatch):
    cases, report, review = fixture()
    dataset = tmp_path / "cases.json"
    dataset.write_text(json.dumps(cases), encoding="utf-8")
    digest = hashlib.sha256(dataset.read_bytes()).hexdigest()
    report.update(dataset_sha256=digest, run_name="baseline-20261028T010300480241Z", publication_verified=True,
                  experiment_url="http://localhost:3300/project/p/experiments/results?baseline=exp",
                  summary={"metrics": {}, "request_failure_rate": 0, "response_p50_seconds": 1, "response_p95_seconds": 1})
    review.update(dataset_sha256=digest, run_name=report["run_name"])
    rp, vp = tmp_path / "baseline.json", tmp_path / "review.json"
    rp.write_text(json.dumps(report), encoding="utf-8")
    vp.write_text(json.dumps(review), encoding="utf-8")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://localhost:3300")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "public")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "secret")
    response = MagicMock(rejected=1, errors=["invalid"])
    response.model_dump.return_value = {"accepted": 3, "rejected": 1, "errors": ["invalid"]}
    client = MagicMock()
    client.api.scores.create.return_value = response
    with patch("aperag.evaluation.adjudication.Langfuse", return_value=client), \
         patch("aperag.evaluation.adjudication.index_items", return_value={"B": SimpleNamespace(trace_id="trace")}):
        with pytest.raises(RuntimeError, match="rejected"):
            publish(rp, dataset, vp)
    persisted = json.loads((tmp_path / "task-adjudication.json").read_text(encoding="utf-8"))
    assert persisted["batch_response"] == {"accepted": 3, "rejected": 1, "errors": ["invalid"]}
    assert persisted["publication_verified"] is False
    client.api.scores.create.assert_called_once()
