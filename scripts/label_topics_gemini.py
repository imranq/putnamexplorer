#!/usr/bin/env python3
import argparse
import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API_URL_TMPL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
BATCH_CREATE_URL_TMPL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:batchGenerateContent"
BATCH_GET_URL_TMPL = "https://generativelanguage.googleapis.com/v1beta/{name}"
FILE_DOWNLOAD_URL_TMPL = "https://generativelanguage.googleapis.com/download/v1beta/{name}:download?alt=media"

TOPICS = [
    "Algebra",
    "Combinatorics",
    "Geometry",
    "Number Theory",
    "Real Analysis",
    "Complex Analysis",
    "Linear Algebra",
    "Probability",
    "Graph Theory",
    "Functional Equations",
    "Inequalities",
    "Calculus",
    "Abstract Algebra",
    "Other",
]

PROBLEM_TYPES = {
    "proof",
    "compute",
    "classify",
    "construct",
    "existence",
    "counterexample",
    "optimization",
    "mixed",
}

ANSWER_FORMATS = {
    "explicit_value",
    "formula",
    "set_characterization",
    "proof_only",
    "asymptotic",
    "algorithm",
    "mixed",
}


def build_prompt(problem_tex: str, solution_tex: str | None = None, include_solution_context: bool = True) -> str:
    topics_str = ", ".join(TOPICS)
    problem_types_str = ", ".join(sorted(PROBLEM_TYPES))
    answer_formats_str = ", ".join(sorted(ANSWER_FORMATS))
    return (
        "Analyze this Putnam problem and output ONLY valid JSON. No markdown, no explanations.\n"
        "Keys required:\n"
        "{\n"
        "  primary_topic,\n"
        "  secondary_topics,\n"
        "  difficulty,\n"
        "  confidence,\n"
        "  problem_type,\n"
        "  answer_format,\n"
        "  techniques,\n"
        "  concepts,\n"
        "  prerequisites,\n"
        "  theorems,\n"
        "  keywords,\n"
        "  estimated_solve_time_minutes,\n"
        "  requires_casework,\n"
        "  requires_construction,\n"
        "  uses_symmetry,\n"
        "  is_multi_part,\n"
        "  difficulty_reason\n"
        "  hints\n"
        "  hint_1,\n"
        "  hint_2,\n"
        "  hint_3\n"
        "}\n"
        "Constraints:\n"
        "- primary_topic must be one of: " + topics_str + "\n"
        "- secondary_topics must be an array of up to 3 topics from the same list, excluding primary_topic\n"
        "- difficulty must be one of: easy, medium, hard, very_hard\n"
        "- confidence must be a number between 0 and 1\n\n"
        "- problem_type must be one of: " + problem_types_str + "\n"
        "- answer_format must be one of: " + answer_formats_str + "\n"
        "- techniques: array of up to 6 short strings (methods used)\n"
        "- concepts: array of up to 8 short strings (mathematical objects/ideas)\n"
        "- prerequisites: array of up to 6 short strings\n"
        "- theorems: array of up to 4 theorem names (or empty)\n"
        "- keywords: array of up to 10 lowercase short tags\n"
        "- estimated_solve_time_minutes: integer between 15 and 240\n"
        "- requires_casework/requires_construction/uses_symmetry/is_multi_part: booleans\n"
        "- difficulty_reason: one sentence, <= 25 words\n\n"
        "- hints: array of 1 to 3 progressive hints, each <= 25 words, no final answer\n"
        "- hint_1, hint_2, hint_3: same hints split into explicit fields; use null when unavailable\n\n"
        "Important hint rule:\n"
        "- Hints must not reveal the final trick, final formula, or final proof structure directly.\n\n"
        "Problem TeX:\n" + problem_tex
    )
    if include_solution_context and solution_tex:
        prompt += (
            "\n\nOfficial Solution Context (for topic/difficulty/hint quality only):\n"
            + solution_tex
            + "\n\nUse solution context to improve metadata quality, but keep hints non-spoiler."
        )
    return prompt


def extract_json(text: str):
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.S)
    if fence:
        text = fence.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON object in model response")
    return json.loads(text[start : end + 1])


def call_gemini(api_key: str, model: str, prompt: str):
    url = API_URL_TMPL.format(model=model, api_key=api_key)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    parts = body.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    if not parts:
        raise ValueError(f"No candidate content: {body}")
    text = "\n".join(p.get("text", "") for p in parts)
    parsed = extract_json(text)
    return {
        "parsed": parsed,
        "raw_text": text,
        "raw_body": body,
    }


def _request_json(method: str, url: str, api_key: str, payload: dict | None = None):
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def _request_bytes(method: str, url: str, api_key: str):
    headers = {"x-goog-api-key": api_key}
    req = urllib.request.Request(url, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=180) as resp:
        return resp.read()


def _normalize_model(model: str) -> str:
    return model[len("models/") :] if model.startswith("models/") else model


def _response_text_from_generate_content_response(response_obj: dict) -> str:
    if not isinstance(response_obj, dict):
        return ""
    if "text" in response_obj and isinstance(response_obj["text"], str):
        return response_obj["text"]
    texts = []
    for cand in response_obj.get("candidates", []):
        content = cand.get("content", {})
        for part in content.get("parts", []):
            txt = part.get("text")
            if isinstance(txt, str):
                texts.append(txt)
    return "\n".join(texts).strip()


def _chunk_requests(requests: list, max_bytes: int, max_count: int):
    chunks = []
    cur = []
    cur_bytes = 2
    for item in requests:
        item_bytes = len(json.dumps(item, ensure_ascii=False).encode("utf-8")) + 1
        if cur and (len(cur) >= max_count or cur_bytes + item_bytes > max_bytes):
            chunks.append(cur)
            cur = []
            cur_bytes = 2
        cur.append(item)
        cur_bytes += item_bytes
    if cur:
        chunks.append(cur)
    return chunks


def create_batch_job(api_key: str, model: str, wrapped_requests: list, display_name: str):
    payload = {
        "batch": {
            "display_name": display_name,
            "input_config": {
                "requests": {
                    "requests": wrapped_requests
                }
            },
        }
    }
    model_id = _normalize_model(model)
    url = BATCH_CREATE_URL_TMPL.format(model=urllib.parse.quote(model_id, safe=""))
    return _request_json("POST", url, api_key, payload)


def get_batch_job(api_key: str, batch_name: str):
    url = BATCH_GET_URL_TMPL.format(name=urllib.parse.quote(batch_name, safe="/"))
    return _request_json("GET", url, api_key)


def download_batch_file(api_key: str, file_name: str) -> bytes:
    url = FILE_DOWNLOAD_URL_TMPL.format(name=urllib.parse.quote(file_name, safe="/"))
    return _request_bytes("GET", url, api_key)


def _extract_batch_name(create_resp: dict) -> str | None:
    name = create_resp.get("name")
    if isinstance(name, str) and name.startswith("batches/"):
        return name
    meta = create_resp.get("metadata", {})
    if isinstance(meta, dict):
        mname = meta.get("name")
        if isinstance(mname, str) and mname.startswith("batches/"):
            return mname
    resp = create_resp.get("response", {})
    if isinstance(resp, dict):
        rname = resp.get("name")
        if isinstance(rname, str) and rname.startswith("batches/"):
            return rname
    return None


def _extract_batch_obj(status_resp: dict) -> dict:
    resp = status_resp.get("response")
    return resp if isinstance(resp, dict) else status_resp


def _extract_batch_state(status_resp: dict) -> str:
    meta = status_resp.get("metadata", {})
    if isinstance(meta, dict):
        state = meta.get("state") or meta.get("status")
        if isinstance(state, str) and state:
            return state
    batch_obj = _extract_batch_obj(status_resp)
    meta2 = batch_obj.get("metadata", {})
    if isinstance(meta2, dict):
        state2 = meta2.get("state") or meta2.get("status")
        if isinstance(state2, str) and state2:
            return state2
    if status_resp.get("done"):
        return "DONE"
    return "UNKNOWN"


def _extract_inlined_responses(batch_obj: dict):
    candidates = [
        batch_obj.get("metadata", {}).get("output", {}).get("inlinedResponses", {}).get("inlinedResponses"),
        batch_obj.get("metadata", {}).get("output", {}).get("inlined_responses", {}).get("inlined_responses"),
        batch_obj.get("output", {}).get("inlinedResponses", {}).get("inlinedResponses"),
        batch_obj.get("output", {}).get("inlined_responses", {}).get("inlined_responses"),
        batch_obj.get("dest", {}).get("inlinedResponses", {}).get("responses"),
        batch_obj.get("dest", {}).get("inlined_responses", {}).get("responses"),
        batch_obj.get("inlinedResponses", {}).get("responses"),
        batch_obj.get("inlined_responses", {}).get("responses"),
    ]
    for c in candidates:
        if isinstance(c, list):
            return c
    return []


def _extract_responses_file_ref(batch_obj: dict):
    candidates = [
        batch_obj.get("metadata", {}).get("output", {}).get("responsesFile", {}).get("name"),
        batch_obj.get("metadata", {}).get("output", {}).get("responses_file", {}).get("name"),
        batch_obj.get("metadata", {}).get("output", {}).get("responsesFile", {}).get("uri"),
        batch_obj.get("metadata", {}).get("output", {}).get("responses_file", {}).get("uri"),
        batch_obj.get("metadata", {}).get("output", {}).get("responsesFileUri"),
        batch_obj.get("metadata", {}).get("output", {}).get("responses_file_uri"),
        batch_obj.get("output", {}).get("responsesFile", {}).get("name"),
        batch_obj.get("output", {}).get("responses_file", {}).get("name"),
        batch_obj.get("output", {}).get("responsesFile", {}).get("uri"),
        batch_obj.get("output", {}).get("responses_file", {}).get("uri"),
        batch_obj.get("output", {}).get("responsesFileUri"),
        batch_obj.get("output", {}).get("responses_file_uri"),
        batch_obj.get("dest", {}).get("responsesFile", {}).get("name"),
        batch_obj.get("dest", {}).get("responses_file", {}).get("name"),
        batch_obj.get("dest", {}).get("responsesFile", {}).get("uri"),
        batch_obj.get("dest", {}).get("responses_file", {}).get("uri"),
        batch_obj.get("responsesFile", {}).get("name"),
        batch_obj.get("responses_file", {}).get("name"),
        batch_obj.get("responsesFile", {}).get("uri"),
        batch_obj.get("responses_file", {}).get("uri"),
    ]
    for c in candidates:
        if isinstance(c, str) and c:
            return c
    return None


def download_batch_output(api_key: str, file_ref: str) -> bytes:
    if file_ref.startswith("files/"):
        return download_batch_file(api_key, file_ref)
    if file_ref.startswith("http://") or file_ref.startswith("https://"):
        return _request_bytes("GET", file_ref, api_key)
    # Unknown ref shape; attempt as file name anyway.
    return download_batch_file(api_key, file_ref)


def _extract_item_key(item: dict, fallback_idx: int) -> str:
    meta = item.get("metadata", {})
    if isinstance(meta, dict):
        key = meta.get("key")
        if isinstance(key, str) and key:
            return key
    key = item.get("key")
    if isinstance(key, str) and key:
        return key
    return f"idx:{fallback_idx}"


def _extract_item_response(item: dict):
    if isinstance(item.get("response"), dict):
        return item["response"]
    if isinstance(item.get("generateContentResponse"), dict):
        return item["generateContentResponse"]
    return item


def _extract_batch_progress(status_resp: dict) -> dict:
    """
    Best-effort extraction across possible response shapes.
    """
    batch_obj = _extract_batch_obj(status_resp)

    candidates = []
    for root in (status_resp, batch_obj):
        if isinstance(root, dict):
            candidates.append(root.get("metadata"))
            candidates.append(root.get("batchStats"))
            candidates.append(root.get("batch_stats"))
            candidates.append(root.get("stats"))
            md = root.get("metadata")
            if isinstance(md, dict):
                candidates.append(md.get("batchStats"))
                candidates.append(md.get("batch_stats"))
                candidates.append(md.get("stats"))

    completed = failed = running = pending = total = None
    key_sets = [
        ("completedRequests", "failedRequests", "runningRequests", "pendingRequests", "totalRequests"),
        ("completed_requests", "failed_requests", "running_requests", "pending_requests", "total_requests"),
        ("completed", "failed", "running", "pending", "total"),
    ]

    def _as_int(v):
        try:
            return int(v)
        except Exception:
            return None

    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        for ck, fk, rk, pk, tk in key_sets:
            c = _as_int(cand.get(ck))
            f = _as_int(cand.get(fk))
            r = _as_int(cand.get(rk))
            p = _as_int(cand.get(pk))
            t = _as_int(cand.get(tk))
            if any(v is not None for v in (c, f, r, p, t)):
                if completed is None:
                    completed = c
                if failed is None:
                    failed = f
                if running is None:
                    running = r
                if pending is None:
                    pending = p
                if total is None:
                    total = t

    if total is None:
        # Fallback: infer total from known counts if possible.
        parts = [x for x in (completed, failed, running, pending) if isinstance(x, int)]
        if len(parts) >= 2:
            total = sum(parts)

    return {
        "completed": completed,
        "failed": failed,
        "running": running,
        "pending": pending,
        "total": total,
    }


def _format_progress(progress: dict) -> str:
    c = progress.get("completed")
    f = progress.get("failed")
    r = progress.get("running")
    p = progress.get("pending")
    t = progress.get("total")

    chunks = []
    if c is not None and t is not None:
        chunks.append(f"completed={c}/{t}")
    elif c is not None:
        chunks.append(f"completed={c}")
    if f is not None:
        chunks.append(f"failed={f}")
    if r is not None:
        chunks.append(f"running={r}")
    if p is not None:
        chunks.append(f"pending={p}")
    return ", ".join(chunks)


def append_jsonl(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _clean_string_list(value, limit):
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        if not isinstance(item, str):
            continue
        s = item.strip()
        if not s:
            continue
        out.append(s)
    # Deduplicate preserving order.
    deduped = list(dict.fromkeys(out))
    return deduped[:limit]


def _as_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"true", "yes", "1"}:
            return True
        if v in {"false", "no", "0"}:
            return False
    return default


def normalize_label(obj):
    primary = obj.get("primary_topic", "Other")
    if primary not in TOPICS:
        primary = "Other"

    secondary = obj.get("secondary_topics", [])
    if not isinstance(secondary, list):
        secondary = []
    secondary = [t for t in secondary if t in TOPICS and t != primary][:3]

    difficulty = obj.get("difficulty", "hard")
    if difficulty not in {"easy", "medium", "hard", "very_hard"}:
        difficulty = "hard"

    conf = obj.get("confidence", 0.5)
    try:
        conf = float(conf)
    except Exception:
        conf = 0.5
    conf = max(0.0, min(1.0, conf))

    problem_type = obj.get("problem_type", "mixed")
    if problem_type not in PROBLEM_TYPES:
        problem_type = "mixed"

    answer_format = obj.get("answer_format", "mixed")
    if answer_format not in ANSWER_FORMATS:
        answer_format = "mixed"

    techniques = _clean_string_list(obj.get("techniques", []), 6)
    concepts = _clean_string_list(obj.get("concepts", []), 8)
    prerequisites = _clean_string_list(obj.get("prerequisites", []), 6)
    theorems = _clean_string_list(obj.get("theorems", []), 4)
    keywords = [k.lower() for k in _clean_string_list(obj.get("keywords", []), 10)]

    est = obj.get("estimated_solve_time_minutes", 90)
    try:
        est = int(est)
    except Exception:
        est = 90
    est = max(15, min(240, est))

    requires_casework = _as_bool(obj.get("requires_casework"), False)
    requires_construction = _as_bool(obj.get("requires_construction"), False)
    uses_symmetry = _as_bool(obj.get("uses_symmetry"), False)
    is_multi_part = _as_bool(obj.get("is_multi_part"), False)

    difficulty_reason = obj.get("difficulty_reason", "")
    if not isinstance(difficulty_reason, str):
        difficulty_reason = ""
    difficulty_reason = difficulty_reason.strip()
    if len(difficulty_reason.split()) > 25:
        difficulty_reason = " ".join(difficulty_reason.split()[:25])

    hints = _clean_string_list(obj.get("hints", []), 3)
    hint_1 = obj.get("hint_1")
    hint_2 = obj.get("hint_2")
    hint_3 = obj.get("hint_3")
    explicit_hints = []
    for hint in [hint_1, hint_2, hint_3]:
        if isinstance(hint, str) and hint.strip():
            explicit_hints.append(hint.strip())
    explicit_hints = _clean_string_list(explicit_hints, 3)
    if explicit_hints:
        hints = explicit_hints
    if not hints:
        hints = ["Identify the core structure and restate the goal in an equivalent form."]
    hint_1 = hints[0] if len(hints) > 0 else None
    hint_2 = hints[1] if len(hints) > 1 else None
    hint_3 = hints[2] if len(hints) > 2 else None

    return {
        "topic": primary,
        "secondary_topics": secondary,
        "difficulty": difficulty,
        "topic_confidence": conf,
        "problem_type": problem_type,
        "answer_format": answer_format,
        "techniques": techniques,
        "concepts": concepts,
        "prerequisites": prerequisites,
        "theorems": theorems,
        "keywords": keywords,
        "estimated_solve_time_minutes": est,
        "requires_casework": requires_casework,
        "requires_construction": requires_construction,
        "uses_symmetry": uses_symmetry,
        "is_multi_part": is_multi_part,
        "difficulty_reason": difficulty_reason,
        "hints": hints,
        "hint_1": hint_1,
        "hint_2": hint_2,
        "hint_3": hint_3,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/processed/problems.json")
    parser.add_argument("--output", default="data/processed/problems.labeled.json")
    parser.add_argument("--model", default="gemini-3.1-flash-lite-preview")
    parser.add_argument("--mode", choices=["batch", "sync"], default="batch")
    parser.add_argument("--delay", type=float, default=0.4)
    parser.add_argument("--poll-interval", type=float, default=20.0)
    parser.add_argument("--batch-max-requests", type=int, default=200)
    parser.add_argument("--batch-max-bytes", type=int, default=15_000_000)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-solution-context", action="store_true")
    parser.add_argument("--log-dir", default="logs/label_runs")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("Set GEMINI_API_KEY first.")

    in_path = Path(args.input)
    data = json.loads(in_path.read_text(encoding="utf-8"))

    started_at = datetime.now(timezone.utc)
    run_id = started_at.strftime("%Y%m%dT%H%M%SZ")
    log_dir = Path(args.log_dir) / run_id
    successes_log = log_dir / "successes.jsonl"
    failures_log = log_dir / "failures.jsonl"
    run_log = log_dir / "run.json"

    updated = 0
    seen = 0
    skipped = 0
    failures = 0

    run_meta = {
        "run_id": run_id,
        "started_at": started_at.isoformat(),
        "input": str(Path(args.input).resolve()),
        "output": str(Path(args.output).resolve()),
        "model": args.model,
        "delay": args.delay,
        "poll_interval": args.poll_interval,
        "mode": args.mode,
        "limit": args.limit,
        "force": args.force,
        "include_solution_context": not args.no_solution_context,
        "successes_log": str(successes_log.resolve()),
        "failures_log": str(failures_log.resolve()),
    }
    log_dir.mkdir(parents=True, exist_ok=True)
    run_log.write_text(json.dumps(run_meta, indent=2), encoding="utf-8")
    print(f"Run log dir: {log_dir}")

    selected = []
    for rec in data.get("problems", []):
        seen += 1
        if not args.force and rec.get("topic"):
            skipped += 1
            continue
        selected.append(rec)
        if args.limit and len(selected) >= args.limit:
            break

    if args.mode == "sync":
        for rec in selected:
            prompt = build_prompt(
                rec["problem_tex"],
                rec.get("solution_tex"),
                include_solution_context=(not args.no_solution_context),
            )
            model_out = None
            try:
                model_out = call_gemini(api_key, args.model, prompt)
                normalized = normalize_label(model_out["parsed"])
                rec.update(normalized)
                updated += 1
                event = {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "id": rec["id"],
                    "topic": rec.get("topic"),
                    "confidence": rec.get("topic_confidence"),
                    "difficulty": rec.get("difficulty"),
                    "raw_text": model_out.get("raw_text", ""),
                }
                append_jsonl(successes_log, event)
                print(f"[OK {updated}] {rec['id']} -> {rec['topic']} ({rec['topic_confidence']:.2f})")
            except Exception as exc:
                failures += 1
                failure_event = {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "id": rec.get("id"),
                    "error": str(exc),
                    "problem_tex": rec.get("problem_tex", ""),
                    "prompt": prompt,
                    "raw_text": (model_out or {}).get("raw_text"),
                    "raw_body": (model_out or {}).get("raw_body"),
                }
                append_jsonl(failures_log, failure_event)
                print(f"[FAIL {failures}] {rec['id']}: {exc}")
            time.sleep(args.delay)
    else:
        wrapped = []
        rec_by_id = {}
        prompt_by_id = {}
        for rec in selected:
            prompt = build_prompt(
                rec["problem_tex"],
                rec.get("solution_tex"),
                include_solution_context=(not args.no_solution_context),
            )
            rid = rec["id"]
            rec_by_id[rid] = rec
            prompt_by_id[rid] = prompt
            wrapped.append(
                {
                    "request": {
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.1},
                    },
                    "metadata": {"key": rid},
                }
            )

        chunks = _chunk_requests(wrapped, args.batch_max_bytes, args.batch_max_requests)
        print(f"Submitting {len(wrapped)} requests across {len(chunks)} batch job(s).")

        for i, chunk in enumerate(chunks, start=1):
            display_name = f"putnam-label-{run_id}-{i}"
            create_resp = create_batch_job(api_key, args.model, chunk, display_name)
            batch_name = _extract_batch_name(create_resp)
            if not batch_name:
                failures += len(chunk)
                append_jsonl(
                    failures_log,
                    {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "id": None,
                        "error": "Could not parse batch name from create response.",
                        "create_response": create_resp,
                        "chunk_index": i,
                    },
                )
                print(f"[FAIL] batch {i}: could not extract batch name")
                continue

            print(f"[BATCH {i}/{len(chunks)}] submitted: {batch_name} ({len(chunk)} requests)")
            status = get_batch_job(api_key, batch_name)
            while True:
                state = _extract_batch_state(status).upper()
                progress = _extract_batch_progress(status)
                progress_str = _format_progress(progress)
                if state in {
                    "SUCCEEDED",
                    "JOB_STATE_SUCCEEDED",
                    "BATCH_STATE_SUCCEEDED",
                    "DONE",
                }:
                    break
                if state in {
                    "FAILED",
                    "CANCELLED",
                    "JOB_STATE_FAILED",
                    "JOB_STATE_CANCELLED",
                    "BATCH_STATE_FAILED",
                    "BATCH_STATE_CANCELLED",
                }:
                    break
                if progress_str:
                    print(f"[BATCH {i}] state={state}; {progress_str}; sleeping {args.poll_interval:.1f}s")
                else:
                    print(f"[BATCH {i}] state={state}; sleeping {args.poll_interval:.1f}s")
                time.sleep(args.poll_interval)
                status = get_batch_job(api_key, batch_name)

            final_state = _extract_batch_state(status).upper()
            final_progress = _format_progress(_extract_batch_progress(status))
            if final_progress:
                print(f"[BATCH {i}] final state={final_state}; {final_progress}")
            else:
                print(f"[BATCH {i}] final state={final_state}")
            if final_state in {
                "FAILED",
                "CANCELLED",
                "JOB_STATE_FAILED",
                "JOB_STATE_CANCELLED",
                "BATCH_STATE_FAILED",
                "BATCH_STATE_CANCELLED",
            }:
                failures += len(chunk)
                append_jsonl(
                    failures_log,
                    {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "id": None,
                        "error": f"Batch ended in non-success state: {final_state}",
                        "batch_name": batch_name,
                        "status": status,
                    },
                )
                print(f"[FAIL] batch {i}: state={final_state}")
                continue

            batch_obj = _extract_batch_obj(status)
            items = _extract_inlined_responses(batch_obj)
            if not items:
                file_ref = _extract_responses_file_ref(batch_obj)
                if file_ref:
                    raw_bytes = download_batch_output(api_key, file_ref)
                    lines = raw_bytes.decode("utf-8", errors="ignore").splitlines()
                    parsed_lines = []
                    for ln in lines:
                        ln = ln.strip()
                        if not ln:
                            continue
                        try:
                            parsed_lines.append(json.loads(ln))
                        except Exception:
                            pass
                    items = parsed_lines

            if not items:
                failures += len(chunk)
                append_jsonl(
                    failures_log,
                    {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "id": None,
                        "error": "No responses found in batch output.",
                        "batch_name": batch_name,
                        "status": status,
                    },
                )
                print(f"[FAIL] batch {i}: no output responses")
                continue

            for idx, item in enumerate(items):
                rid = _extract_item_key(item, idx)
                rec = rec_by_id.get(rid)
                if rec is None:
                    failures += 1
                    append_jsonl(
                        failures_log,
                        {
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "id": rid,
                            "error": "Unknown record id in batch response.",
                            "item": item,
                        },
                    )
                    print(f"[FAIL {failures}] {rid}: unknown id in batch response")
                    continue

                err = item.get("error")
                response_obj = _extract_item_response(item)
                raw_text = _response_text_from_generate_content_response(response_obj)
                try:
                    if err:
                        raise ValueError(f"Batch item error: {err}")
                    parsed = extract_json(raw_text)
                    normalized = normalize_label(parsed)
                    rec.update(normalized)
                    updated += 1
                    append_jsonl(
                        successes_log,
                        {
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "id": rec["id"],
                            "topic": rec.get("topic"),
                            "confidence": rec.get("topic_confidence"),
                            "difficulty": rec.get("difficulty"),
                            "raw_text": raw_text,
                        },
                    )
                    print(f"[OK {updated}] {rec['id']} -> {rec['topic']} ({rec['topic_confidence']:.2f})")
                except Exception as exc:
                    failures += 1
                    append_jsonl(
                        failures_log,
                        {
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "id": rec.get("id"),
                            "error": str(exc),
                            "problem_tex": rec.get("problem_tex", ""),
                            "prompt": prompt_by_id.get(rec.get("id")),
                            "raw_text": raw_text,
                            "item": item,
                        },
                    )
                    print(f"[FAIL {failures}] {rec['id']}: {exc}")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    finished_at = datetime.now(timezone.utc)
    summary = {
        **run_meta,
        "finished_at": finished_at.isoformat(),
        "seen": seen,
        "updated": updated,
        "skipped": skipped,
        "failures": failures,
    }
    run_log.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Processed {seen} records, updated {updated}, skipped {skipped}, failures {failures}.")
    print(f"Wrote labeled output: {out_path}")
    print(f"Success log: {successes_log}")
    print(f"Failure log: {failures_log}")


if __name__ == "__main__":
    main()
