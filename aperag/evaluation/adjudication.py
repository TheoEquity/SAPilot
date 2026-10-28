"""Validate source-based agent reviews and publish them on an existing experiment.

No Bot/model calls, automatic keyword verdicts, or business approval are implied.
The frozen generation report remains unchanged; a separate receipt records review.
"""

import argparse
import hashlib
import json
import math
import os
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import NAMESPACE_URL, uuid5

from dotenv import load_dotenv
from langfuse import Langfuse
from langfuse.api.scores.types.create_score_request import CreateScoreRequest


def unique_index(rows, key):
    indexed = {row[key]: row for row in rows}
    if len(indexed) != len(rows):
        raise ValueError(f"Duplicate {key}")
    return indexed


def adjudicate(cases, report, review, dataset_digest):
    """Bind every ordered criterion to the exact dataset and generated response."""
    if not (review["dataset_sha256"] == report["dataset_sha256"] == dataset_digest):
        raise ValueError("Dataset hash mismatch")
    if review["run_name"] != report["run_name"]:
        raise ValueError("Run mismatch")
    for key in ("reviewer", "review_version", "reviewed_at"):
        if not isinstance(review.get(key), str) or not review[key].strip():
            raise ValueError(f"Missing review {key}")
    if datetime.fromisoformat(review["reviewed_at"]).utcoffset() is None:
        raise ValueError("Review timestamp must include timezone")
    case_map = unique_index(cases, "id")
    results = unique_index(report["results"], "case_id")
    reviews = unique_index(review["cases"], "case_id")
    if (not case_map or set(case_map) != set(results) or set(case_map) != set(reviews)
            or report["expected_cases"] != len(cases) or report["executed_cases"] != len(cases)):
        raise ValueError("Review requires exact complete case coverage")
    decisions = []
    for cid, case in case_map.items():
        row, output, acceptance = reviews[cid], results[cid]["output"], case["acceptance"]
        response = output["response"]
        if hashlib.sha256(response.encode("utf-8")).hexdigest() != row["response_sha256"]:
            raise ValueError(f"Response hash mismatch: {cid}")
        for key in ("must_satisfy", "failure_conditions"):
            if (not isinstance(row.get(key), list) or len(row[key]) != len(acceptance[key])
                    or any(value is not None and type(value) is not bool for value in row[key])):
                raise ValueError(f"Invalid ordered {key}: {cid}")
        for key in ("citation", "runtime_audit"):
            if key not in row or (row[key] is not None and type(row[key]) is not bool):
                raise ValueError(f"Invalid {key}: {cid}")
        quotes = row.get("response_quotes")
        if (not isinstance(row.get("rationale"), str) or not row["rationale"].strip()
                or not isinstance(quotes, list) or (response.strip() and not quotes)
                or any(not isinstance(q, str) or not q.strip()
                       or " ".join(q.split()) not in " ".join(response.split()) for q in quotes)):
            raise ValueError(f"Review needs rationale and literal response quotes: {cid}")
        required = row["must_satisfy"] + [None if v is None else not v for v in row["failure_conditions"]]
        if acceptance["citation_required"]:
            required.append(row["citation"])
        if acceptance["runtime_audit_required"]:
            required.append(row["runtime_audit"])
        status = ("FAIL" if output.get("error") or False in required
                  else "PENDING" if None in required else "PASS")
        decisions.append({**row, "status": status, "scenario": case["scenario"],
                          "runtime_audit_required": acceptance["runtime_audit_required"],
                          "criteria": acceptance})
    return decisions


def task_summary(decisions):
    total = len(decisions)
    counts = Counter(row["status"] for row in decisions)
    return {"total": total, "passed": counts["PASS"], "failed": counts["FAIL"], "pending": counts["PENDING"],
            "confirmed_task_completion_rate": counts["PASS"] / total,
            "task_completion_rate_upper_bound": (counts["PASS"] + counts["PENDING"]) / total,
            "task_review_coverage": (total - counts["PENDING"]) / total,
            "task_completion_rate": counts["PASS"] / total if not counts["PENDING"] else None,
            "audit_pending_count": sum(row["runtime_audit_required"] and row["runtime_audit"] is None
                                       for row in decisions)}


def index_items(lf, experiment_id, started_at, records):
    expected = unique_index(records, "case_id")
    indexed, traces, cursor = {}, set(), None
    while True:
        page = lf.api.experiments.list_items(from_start_time=started_at, experiment_id=experiment_id,
                                             fields="core,io,dataset,scores", limit=100, score_limit=50, cursor=cursor)
        for item in page.data:
            output = json.loads(item.output) if isinstance(item.output, str) else item.output
            cid = output.get("case_id") if isinstance(output, dict) else None
            if cid not in expected or output != expected[cid]:
                raise ValueError("Server output differs from frozen local run")
            if cid in indexed or item.trace_id in traces:
                raise ValueError("Duplicate server case or trace")
            indexed[cid] = item
            traces.add(item.trace_id)
        cursor = page.meta.cursor
        if not cursor:
            break
    if set(indexed) != set(expected):
        raise ValueError("Server case coverage differs from local run")
    return indexed


def check_scores(actual, expected):
    for wanted in expected:
        matches = [score for score in actual if score.id == wanted.id]
        if len(matches) != 1:
            return False
        score = matches[0]
        if score.name != wanted.name or score.data_type != wanted.data_type:
            return False
        if wanted.data_type == "NUMERIC":
            if (type(score.value) not in (int, float) or not math.isfinite(score.value)
                    or not math.isclose(score.value, wanted.value, rel_tol=1e-9, abs_tol=1e-9)):
                return False
        elif score.value != wanted.value:
            return False
        subject = score.subject
        kind, sid = ("trace", wanted.trace_id) if wanted.trace_id else ("experiment", wanted.dataset_run_id)
        if subject is None or subject.kind != kind or subject.id != sid:
            return False
    return True


def score_requests(experiment_id, items, decisions, summary, review, report):
    timestamp = datetime.fromisoformat(review["reviewed_at"])
    metadata = {"reviewer": review["reviewer"], "review_version": review["review_version"],
                "dataset_sha256": review["dataset_sha256"], "business_review": "PENDING"}

    def request(scope, name, value, **kwargs):
        return CreateScoreRequest(id=str(uuid5(NAMESPACE_URL, f"sapilot-acceptance/v1/{scope}/{name}")),
                                  timestamp=timestamp, name=name, value=value,
                                  data_type="CATEGORICAL" if isinstance(value, str) else "NUMERIC",
                                  metadata=metadata, **kwargs)

    per_case = {}
    for row in decisions:
        cid, status = row["case_id"], row["status"]
        values = {"task_status": status, "task_completed_confirmed": float(status == "PASS"),
                  "task_failed": float(status == "FAIL"), "task_pending": float(status == "PENDING")}
        per_case[cid] = [request(f"{experiment_id}/{cid}", name, value, trace_id=items[cid].trace_id,
                                 comment=json.dumps(row, ensure_ascii=False)) for name, value in values.items()]
    metrics = {key: value for key, value in summary.items() if type(value) in (int, float)}
    metrics.update({key: report["summary"][key] for key in
                    ("request_failure_rate", "response_p50_seconds", "response_p95_seconds")})
    for name, metric in report["summary"]["metrics"].items():
        if name.startswith("probe_document_"):
            metrics[name] = metric["mean"]
            metrics[name + "_evaluated"] = metric["evaluated"]
    for scenario in sorted({row["scenario"] for row in decisions}):
        subset = [row for row in decisions if row["scenario"] == scenario]
        metrics[f"{scenario}_confirmed_completion_rate"] = sum(row["status"] == "PASS" for row in subset) / len(subset)
    run_scores = [request(experiment_id, name, float(value), dataset_run_id=experiment_id,
                          comment="Agent review; all cases retained. Pending audits remain unknown. No acceptance threshold set.")
                  for name, value in metrics.items()]
    return per_case, run_scores


def publish(report_path, dataset_path, review_path, timeout_seconds=90):
    report_path, dataset_path, review_path = map(Path, (report_path, dataset_path, review_path))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    review = json.loads(review_path.read_text(encoding="utf-8"))
    cases = json.loads(dataset_path.read_text(encoding="utf-8"))
    decisions = adjudicate(cases, report, review, hashlib.sha256(dataset_path.read_bytes()).hexdigest())
    if not report["publication_verified"]:
        raise ValueError("Generation publication must be verified first")
    url = urlsplit(report["experiment_url"])
    base_url = f"{url.scheme}://{url.netloc}"
    if base_url.rstrip("/") != os.environ.get("LANGFUSE_BASE_URL", "").rstrip("/"):
        raise ValueError("LANGFUSE_BASE_URL must match the original experiment")
    experiment_id = parse_qs(url.query)["baseline"][0]
    started_at = datetime.strptime(report["run_name"], "baseline-%Y%m%dT%H%M%S%fZ").replace(
        tzinfo=timezone.utc) - timedelta(seconds=5)
    summary = task_summary(decisions)
    lf = Langfuse(base_url=base_url, public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
                  secret_key=os.environ["LANGFUSE_SECRET_KEY"])
    artifact = {"run_name": report["run_name"], "experiment_url": report["experiment_url"],
                "dataset_sha256": report["dataset_sha256"], "review_sha256": hashlib.sha256(review_path.read_bytes()).hexdigest(),
                "publisher_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "reviewer": review["reviewer"], "reviewed_at": review["reviewed_at"], "business_review": "PENDING",
                "limitations": review.get("limitations", []),
                "summary": summary, "decisions": decisions, "publication_verified": False}
    target = report_path.with_name("task-adjudication.json")
    try:
        items = index_items(lf, experiment_id, started_at, report["results"])
        per_case, run_scores = score_requests(experiment_id, items, decisions, summary, review, report)
        requests = [score for scores in per_case.values() for score in scores] + run_scores
        # Persist intent before writes. IDs and review timestamp remain stable for recovery.
        target.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        response = lf.api.scores.create(request=requests)
        artifact["batch_response"] = response.model_dump(mode="json")
        if getattr(response, "rejected", 0) or getattr(response, "errors", []):
            raise RuntimeError("Langfuse rejected scores; inspect batch before any retry")
        deadline = time.monotonic() + timeout_seconds
        while True:
            items = index_items(lf, experiment_id, started_at, report["results"])
            runs = lf.api.experiments.list(from_start_time=started_at, id=experiment_id,
                                            fields="core,metadata,scores", limit=100, score_limit=50)
            matching_runs = [run for run in runs.data if run.id == experiment_id]
            if (all(check_scores(items[cid].scores or [], wanted) for cid, wanted in per_case.items())
                    and len(matching_runs) == 1 and check_scores(matching_runs[0].scores or [], run_scores)):
                artifact.update(publication_verified=True, verified_at=datetime.now(timezone.utc).isoformat(),
                                verified_case_count=len(items), verified_score_count=len(requests),
                                verified_run_score_count=len(run_scores))
                break
            if time.monotonic() >= deadline:
                raise TimeoutError("Adjudication score readback incomplete or values differ")
            time.sleep(3)
    except Exception as error:
        artifact["publication_error"] = type(error).__name__
        raise
    finally:
        target.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        lf.shutdown()
    print(json.dumps({"report": str(target), "summary": summary, "verified_scores": len(requests)}, ensure_ascii=False))
    return artifact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--reviews", required=True)
    parser.add_argument("--env-file", action="append", default=[])
    args = parser.parse_args()
    for path in args.env_file:
        load_dotenv(path, override=True)
    publish(args.report, args.dataset, args.reviews)


if __name__ == "__main__":
    main()
