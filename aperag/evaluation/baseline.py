"""Run versioned SAPilot Bot evaluations in a self-hosted Langfuse project.

Uses the real session-authenticated WebSocket API. Final citations are never
treated as ranked retrieval. Optional collection search probes are labelled
separately. The existing Ragas runner supplies semantic evaluation.
"""

import argparse
import asyncio
import hashlib
import json
import math
import os
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import httpx
from dotenv import load_dotenv
from langfuse import Evaluation, Langfuse
from websockets.sync.client import connect

# Evaluator data and telemetry stay in the configured services.
os.environ["RAGAS_DO_NOT_TRACK"] = "true"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"

from aperag.evaluation.run import EvaluationRunner  # noqa: E402


def load_cases(path):
    """Require explicit IDs and expectations; preserve repeated questions."""
    cases = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise ValueError("Dataset must be a nonempty JSON array")
    ids = set()
    for case in cases:
        for field in ("id", "question", "answer", "scenario", "expected_action"):
            if not isinstance(case.get(field), str) or not case[field].strip():
                raise ValueError(f"Each case requires nonempty {field}")
        if case["id"] in ids:
            raise ValueError(f"Duplicate case ID: {case['id']}")
        ids.add(case["id"])
        if case["expected_action"] not in {"answer", "clarify", "refuse"}:
            raise ValueError("expected_action must be answer, clarify or refuse")
        for field in ("relevant_document_ids", "required_identifiers"):
            if field in case and (not isinstance(case[field], list) or
                                  any(not isinstance(value, str) or not value for value in case[field])):
                raise ValueError(f"{field} must be a list of nonempty strings")
    return cases


def retrieval_scores(items, relevant_ids):
    """Document-level metrics: deduplicate documents before applying K."""
    relevant = set(relevant_ids or [])
    if not relevant:
        return {}  # unlabelled is unknown, not zero
    ranked = []
    for item in items:
        document_id = (item.get("metadata") or {}).get("document_id")
        if not document_id:
            raise ValueError("Search result is missing metadata.document_id")
        if document_id not in ranked:
            ranked.append(document_id)
    scores = {f"probe_document_recall_at_{k}": len(set(ranked[:k]) & relevant) / len(relevant)
              for k in (1, 3, 5)}
    scores["probe_document_mrr_at_5"] = next(
        (1 / rank for rank, doc in enumerate(ranked[:5], 1) if doc in relevant), 0.0
    )
    return scores


def citation_contexts(references):
    """Only explicit evidence text; never stringify titles or metadata as context."""
    return [{"text": reference.get("text") or reference.get("content")}
            for reference in references
            if isinstance(reference, dict) and
            isinstance(reference.get("text") or reference.get("content"), str) and
            (reference.get("text") or reference.get("content")).strip()]


def validate_langfuse_destination(config):
    """A supplied self-host config must never silently use an ambient cloud URL."""
    expected = config["langfuse_base_url"].rstrip("/")
    actual = os.environ.get("LANGFUSE_BASE_URL", "").rstrip("/")
    if not expected or actual != expected:
        raise ValueError("LANGFUSE_BASE_URL must match config.langfuse_base_url")
    return expected


class BotClient:
    def __init__(self, config):
        self.config = config
        self.base_url = config["base_url"].rstrip("/")
        self.timeout = config.get("timeout_seconds", 180)
        session = config.get("session_cookie")
        self.http = httpx.Client(base_url=self.base_url + "/", timeout=self.timeout,
                                 cookies={"session": session} if session else None)
        if not session:
            username, password = config.get("username"), config.get("password")
            if not username or not password:
                raise ValueError("Set api.session_cookie or api.username and api.password")
            response = self.http.post("login", json={"username": username, "password": password})
            response.raise_for_status()
        self.session = self.http.cookies.get("session")
        if not self.session:
            raise ValueError("SAPilot login returned no session cookie")

    def close(self):
        self.http.close()

    def run(self, bot_id, case):
        started = time.perf_counter()
        output = {"response": "", "context": [], "error": None, "citations": [],
                  "context_origin": "final_citations", "chat_id": None,
                  "response_time": 0.0, "first_token_seconds": None}
        try:
            response = self.http.post(f"bots/{bot_id}/chats")
            response.raise_for_status()
            chat_id = response.json()["id"]
            output["chat_id"] = chat_id
            ws_base = self.base_url.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
            url = f"{ws_base}/bots/{bot_id}/chats/{chat_id}/connect"
            deadline = time.monotonic() + self.timeout
            with connect(url, additional_headers={"Cookie": f"session={self.session}"},
                         open_timeout=self.timeout, max_size=16 * 1024 * 1024) as websocket:
                # Both Agent and traditional Flow Bots accept these respective fields.
                websocket.send(json.dumps({"query": case["question"], "data": case["question"],
                                           "collections": [], "language": "zh-CN"}))
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("Bot response timed out before stop")
                    event = json.loads(websocket.recv(timeout=remaining))
                    kind = event.get("type")
                    if kind in {"error", "fail"}:
                        raise RuntimeError("Bot returned an error event")
                    if kind == "message" and isinstance(event.get("data"), str):
                        if event["data"] and output["first_token_seconds"] is None:
                            output["first_token_seconds"] = time.perf_counter() - started
                        output["response"] += event["data"]
                    if kind == "references" or (kind == "stop" and isinstance(event.get("data"), list)):
                        output["citations"].extend(event.get("data") or [])
                    if kind == "stop":
                        break
            if not output["response"].strip():
                raise RuntimeError("Bot returned an empty answer")
            output["context"] = citation_contexts(output["citations"])
        except Exception as error:
            # Never include credentials, URLs with tokens, or response bodies in reports.
            output["error"] = type(error).__name__
        output["response_time"] = time.perf_counter() - started
        return output

    def probe(self, case, config):
        collection_id = case.get("collection_id") or config.get("collection_id")
        if not collection_id:
            raise ValueError("Retrieval probe requires a collection_id")
        response = self.http.post(f"collections/{collection_id}/searches",
                                  json={**config["search"], "query": case["question"]})
        response.raise_for_status()
        return response.json()["items"]


def summarize(results):
    total = len(results)
    failures = sum(bool(row["output"].get("error")) for row in results)
    metric_names = {name for row in results for name in row["scores"]}
    metrics = {}
    for name in sorted(metric_names):
        values = [row["scores"][name] for row in results if name in row["scores"]]
        metrics[name] = {"mean": sum(values) / len(values), "evaluated": len(values), "total": total}
    durations = sorted(row["output"]["response_time"] for row in results)
    return {"total": total, "request_failures": failures,
            "request_failure_rate": failures / total if total else None,
            "response_p50_seconds": durations[math.ceil(total * .5) - 1] if total else None,
            "response_p95_seconds": durations[math.ceil(total * .95) - 1] if total else None,
            "metrics": metrics,
            "task_pass_rate": None,
            "task_pass_rate_note": "Not established: requires reviewed per-case acceptance and calibrated judges; no thresholds set."}


class BaselineRunner(EvaluationRunner):
    """Reuse existing Ragas setup and scoring without the unimplemented endpoint."""

    def evaluate_case(self, case, output):
        scores = {"request_success": float(not output["error"])}
        notes = []
        if output["error"]:
            return scores, ["Request failed; retained in total denominator"]
        identifiers = case.get("required_identifiers")
        if identifiers:
            scores["required_identifier_coverage"] = sum(
                identifier in output["response"] for identifier in identifiers
            ) / len(identifiers)
        if case["expected_action"] != "answer":
            return scores, ["Correct refusal/clarification requires human review; not scored as a wrong answer"]
        requested = self.config["metrics"]
        # A final citation is not the full LLM context. Name its scope explicitly.
        context_metrics = {"faithfulness", "context_precision", "context_recall"}
        if not output["context"]:
            notes.append("No citation evidence text: context metrics unavailable")
            requested = [name for name in requested if name not in context_metrics]
        if requested:
            records = asyncio.run(self._run_ragas_evaluation(
                [{**output, "question": case["question"], "ground_truth": case["answer"]}], requested))
            if not records:
                notes.append("Ragas evaluation failed or yielded no scores")
            else:
                for metric in requested:
                    keys = [key for key in records[0] if key == metric or key.startswith(metric + "(")]
                    value = records[0].get(keys[0]) if keys else None
                    if isinstance(value, (int, float)) and math.isfinite(value):
                        prefix = "ragas_cited_" if metric in context_metrics else "ragas_"
                        scores[prefix + metric] = float(value)
                    else:
                        notes.append(f"Ragas {metric} unavailable; not replaced with zero")
        return scores, notes


def execute(config_path):
    config_path = Path(config_path).resolve()
    runner = BaselineRunner(config_path)
    config = runner.config
    # All unresolved environment variables fail before any data is sent.
    if "${" in json.dumps(config):
        raise ValueError("Unresolved environment variables in evaluation config")
    langfuse_url = validate_langfuse_destination(config)
    dataset_path = (config_path.parent / config["dataset_path"]).resolve()
    cases = load_cases(dataset_path)
    digest = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    dataset_name = f"{config['dataset_name']}/{digest[:12]}"
    started_at = datetime.now(timezone.utc) - timedelta(seconds=5)
    run_name = datetime.now(timezone.utc).strftime("baseline-%Y%m%dT%H%M%S%fZ")
    report_dir = (config_path.parent / config["report_dir"] / run_name).resolve()
    report_dir.mkdir(parents=True, exist_ok=False)
    lf = Langfuse(base_url=langfuse_url,
                  public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
                  secret_key=os.environ["LANGFUSE_SECRET_KEY"])
    client = None
    results = []
    experiment = None
    publication_error = None
    metadata = {}
    try:
        if not lf.auth_check():
            raise RuntimeError("Langfuse authentication failed")
        client = BotClient(config["api"])
        bot_response = client.http.get(f"bots/{config['bot_id']}")
        bot_response.raise_for_status()
        # Hash configuration without recording provider credentials.
        bot_config_digest = hashlib.sha256(bot_response.content).hexdigest()
        metadata = {"dataset_sha256": digest, "dataset_version": config["dataset_version"],
                    "rubric_version": config["rubric_version"], "bot_id": config["bot_id"],
                    "bot_snapshot_sha256": bot_config_digest,
                    "runtime_revision": config["runtime_revision"],
                    "knowledge_version": config["knowledge_version"],
                    "evaluator_model": config["llm_for_eval"]["model"],
                    "evaluator_temperature": config["llm_for_eval"]["temperature"],
                    "requested_metrics": config["metrics"],
                    "retrieval_probe": config.get("retrieval_probe"),
                    "evaluator_source_sha256": {name: hashlib.sha256(
                        Path(__file__).with_name(name).read_bytes()).hexdigest()
                        for name in ("baseline.py", "run.py", "requirements.txt")},
                    "evaluator_revision": subprocess.check_output(
                        ["git", "rev-parse", "HEAD"], text=True).strip(),
                    "scope": config["scope"]}
        lf.create_dataset(name=dataset_name, metadata=metadata)
        for case in cases:
            lf.create_dataset_item(dataset_name=dataset_name,
                id=str(uuid5(NAMESPACE_URL, dataset_name + "/" + case["id"])),
                input={"question": case["question"]}, expected_output=case["answer"], metadata=case)

        async def task(*, item, **kwargs):
            case = item.metadata
            output = await asyncio.to_thread(client.run, config["bot_id"], case)
            try:
                scores, notes = await asyncio.to_thread(runner.evaluate_case, case, output)
            except Exception as error:
                scores = {"request_success": float(not output["error"])}
                notes = [f"Evaluator failed: {type(error).__name__}; Bot output retained"]
            probe = config.get("retrieval_probe")
            if probe and case.get("relevant_document_ids"):
                try:
                    items = await asyncio.to_thread(client.probe, case, probe)
                    output["retrieval_probe"] = items
                    scores.update(retrieval_scores(items, case["relevant_document_ids"]))
                except Exception as error:
                    notes.append(f"Independent retrieval probe failed: {type(error).__name__}")
            if not case.get("relevant_document_ids"):
                notes.append("No relevance labels: Recall/MRR unavailable")
            record = {"case_id": case["id"], "scenario": case["scenario"],
                      "expected_action": case["expected_action"], "output": output,
                      "scores": scores, "notes": notes, "human_review": "PENDING"}
            results.append(record)
            (report_dir / f"case-{len(results):04d}.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
            return record

        def evaluator(*, output, **kwargs):
            return [Evaluation(name=name, value=value, data_type="NUMERIC")
                    for name, value in output["scores"].items()]

        experiment = lf.get_dataset(dataset_name).run_experiment(
            name="SAPilot baseline", run_name=run_name, task=task,
            evaluators=[evaluator], max_concurrency=1, metadata=metadata)
        lf.flush()
        # Verify all cases and all expected score names, rather than only HTTP acceptance.
        expected = {row["case_id"]: set(row["scores"]) for row in results}
        deadline = time.monotonic() + config.get("readback_timeout_seconds", 60)
        while True:
            visible = {}
            cursor = None
            while True:
                page = lf.api.experiments.list_items(from_start_time=started_at,
                    experiment_id=experiment.experiment_id, fields="core,io,dataset,scores",
                    limit=100, score_limit=50, cursor=cursor)
                for item in page.data:
                    if isinstance(item.output, dict) and "case_id" in item.output:
                        visible[item.output["case_id"]] = {score.name for score in (item.scores or [])}
                cursor = page.meta.cursor
                if not cursor:
                    break
            if len(expected) == len(cases) and all(names <= visible.get(cid, set()) for cid, names in expected.items()):
                break
            if time.monotonic() >= deadline:
                raise TimeoutError("Langfuse experiment/score readback incomplete")
            time.sleep(3)
    except Exception as error:
        publication_error = type(error).__name__
        raise
    finally:
        summary = {"run_name": run_name, "dataset_name": dataset_name,
                   "dataset_sha256": digest, "scope": config["scope"],
                   "expected_cases": len(cases), "executed_cases": len(results),
                   "metadata": metadata,
                   "publication_verified": publication_error is None and experiment is not None,
                   "publication_error": publication_error,
                   "experiment_url": experiment.experiment_url if experiment else None,
                   "summary": summarize(results), "results": results}
        (report_dir / "baseline.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        if client:
            client.close()
        lf.shutdown()
        print(f"Report: {report_dir / 'baseline.json'}")
    print(f"Langfuse experiment: {experiment.experiment_url}")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--env-file", action="append", default=[])
    args = parser.parse_args()
    for path in args.env_file:
        load_dotenv(path, override=True)
    summary = execute(args.config)
    if summary["summary"]["request_failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
