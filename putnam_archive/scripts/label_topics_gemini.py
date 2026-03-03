#!/usr/bin/env python3
import argparse
import json
import os
import re
import time
import urllib.request
from pathlib import Path

API_URL_TMPL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

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


def build_prompt(problem_tex: str) -> str:
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
        "Problem TeX:\n" + problem_tex
    )


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
    return extract_json(text)


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
    parser.add_argument("--input", default="putnam_archive/data/processed/problems.json")
    parser.add_argument("--output", default="putnam_archive/data/processed/problems.labeled.json")
    parser.add_argument("--model", default="gemini-2.0-flash-lite")
    parser.add_argument("--delay", type=float, default=0.4)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("Set GEMINI_API_KEY first.")

    in_path = Path(args.input)
    data = json.loads(in_path.read_text(encoding="utf-8"))

    updated = 0
    seen = 0
    for rec in data.get("problems", []):
        seen += 1
        if args.limit and updated >= args.limit:
            break
        if not args.force and rec.get("topic"):
            continue

        prompt = build_prompt(rec["problem_tex"])
        try:
            raw = call_gemini(api_key, args.model, prompt)
            normalized = normalize_label(raw)
            rec.update(normalized)
            updated += 1
            print(f"[{updated}] {rec['id']} -> {rec['topic']} ({rec['topic_confidence']:.2f})")
        except Exception as exc:
            print(f"Failed {rec['id']}: {exc}")

        time.sleep(args.delay)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Processed {seen} records, updated {updated}. Wrote {out_path}")


if __name__ == "__main__":
    main()
