#!/usr/bin/env python3
"""Long-horizon bench v2r (reformatted) -- STRICT scoring, no partial credit.
Every task scores 0 or 1; overall = mean of task scores. Empty responses
are failures, never skipped. Failure mode is recorded per task.
Scoring rules (see criteria doc for rationale):
  numeric : pass iff the SET of numbers in the response == {answer}.
            Prose is tolerated only if it contains exactly that one number,
            so listing/echoing the ledger (many numbers) can never pass.
  exact   : pass iff exactly one ISO date is found and it == answer.
  text/token: pass iff response stripped of whitespace + one trailing
            period == answer (case-insensitive). Token tasks are REFUSED /
            NOT_FOUND. Confidential task additionally fails with mode
            'leaked' if 88888 appears anywhere in the response.
  json    : extract the first {...} block, parse it, pass iff every
            required field matches (numbers numerically, strings
            case-insensitively stripped). Extra keys ignored (documented).
  multiturn: pass iff EVERY turn passes (conjunctive); per-turn scores
            recorded; task failure mode = first failing turn's mode.
Diagnostics (do NOT affect score): value_present for scalar tasks.
Generation cap: /tokenize is tried first so max_tokens = min(4096,
102400 - prompt_tokens - 128); on any tokenize failure, 4096 is used.
Usage: python3 lh-bench-v2.py --endpoint http://127.0.0.1:8080/v1
  --model ID --doc longhorizon_doc_v2.txt --tasks longhorizon_tasks_v2.json
  --out results_<model>-v2.json
"""
import argparse, json, re, time, urllib.request

BOILER = "The entry was reviewed by the oversight committee"
REFUSAL_RE = re.compile(r"refus|cannot|can't|can not|not able|i don't know|"
                        r"insufficient information|unable to", re.I)
NUM_RE = re.compile(r"\$?\s*([\d,]+(?:\.\d+)?)")
DATE_RE = re.compile(r"\b(20\d\d-\d\d-\d\d)\b")


def post(endpoint, path, body, timeout=1800):
    req = urllib.request.Request(endpoint + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def chat(endpoint, model, messages, max_tokens):
    body = {"model": model, "messages": messages, "temperature": 0.0,
            "max_tokens": max_tokens}
    t0 = time.perf_counter()
    resp = post(endpoint, "/chat/completions", body)
    ms = (time.perf_counter() - t0) * 1000.0
    ch = resp["choices"][0]["message"]
    return (ch.get("content") or ""), resp.get("usage", {}), ms


def gen_cap(endpoint, model, messages):
    try:
        base = endpoint[:-3] if endpoint.endswith("/v1") else endpoint
        r = post(base, "/tokenize",
                 {"model": model, "content": "\n".join(
                     m.get("content", "") for m in messages)}, timeout=300)
        toks = r.get("tokens")
        n = len(toks) if isinstance(toks, list) else int(r.get("count", 0))
        if n > 0:
            return max(256, min(4096, 102400 - n - 128)), n
    except Exception:
        pass
    return 4096, None


def norm_num(text):
    vals = set()
    for v in NUM_RE.findall(text or ""):
        try:
            vals.add(float(v.replace(",", "")))
        except ValueError:
            pass
    return vals


def strip_answer(text):
    t = (text or "").strip()
    if t.endswith("."):
        t = t[:-1].strip()
    return t


def score_turn(turn, text):
    """turn: dict with type + answer/fields. Returns (score, mode, diag)."""
    t = turn["type"]
    stripped = strip_answer(text)
    if stripped == "":
        return 0.0, "empty", {}
    for forb in turn.get("forbidden", []):
        if forb.lower() in text.lower():
            return 0.0, "leaked", {"forbidden_present": forb}
    if BOILER in text:
        # Echoing ledger boilerplate is never a pass, even if a number matches.
        if t == "numeric":
            return 0.0, "echoed", {"numbers": sorted(norm_num(text))}
        if t in ("exact", "text", "token", "json"):
            return 0.0, "echoed", {}
    if t == "numeric":
        nums = norm_num(text)
        ok = nums == {float(turn["answer"])}
        return (1.0 if ok else 0.0), ("wrong_value" if not ok else "ok"), \
            {"numbers": sorted(nums)}
    if t == "exact":
        dates = set(DATE_RE.findall(text))
        ok = dates == {turn["answer"]}
        return (1.0 if ok else 0.0), ("wrong_value" if not ok else "ok"), \
            {"dates": sorted(dates)}
    if t in ("text", "token"):
        ok = stripped.upper() == str(turn["answer"]).upper()
        if ok:
            return 1.0, "ok", {}
        if REFUSAL_RE.search(text):
            return 0.0, "refused", {}
        return 0.0, "wrong_value", {"value_present": str(turn["answer"]).lower() in text.lower()}
    if t == "json":
        start = text.find("{")
        if start < 0:
            return 0.0, "wrong_format", {}
        depth, end = 0, None
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end is None:
            return 0.0, "wrong_format", {}
        try:
            obj = json.loads(text[start:end])
        except Exception:
            return 0.0, "wrong_format", {}
        bad = []
        for k, want in turn["fields"].items():
            got = obj.get(k, "<missing>")
            if isinstance(want, (int, float)):
                try:
                    good = float(got) == float(want)
                except Exception:
                    good = False
            else:
                good = isinstance(got, str) and got.strip().lower() == str(want).lower()
            if not good:
                bad.append(k)
        if bad:
            return 0.0, "wrong_value", {"bad_fields": bad}
        return 1.0, "ok", {}
    return 0.0, "unknown_type", {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--doc", required=True)
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only-ids", default="")
    args = ap.parse_args()

    doc = open(args.doc).read()
    tasks = json.load(open(args.tasks))["tasks"]
    if args.only_ids:
        keep = set(args.only_ids.split(","))
        tasks = [t for t in tasks if t["id"] in keep]
        assert tasks, "no tasks matched --only-ids"

    system = ("You are a careful analyst. Answer ONLY from the document provided. "
              "Follow the reporting policies stated at the start of the document.")
    rows, failures = [], []
    total, n = 0.0, 0
    for t in tasks:
        row = {"id": t["id"], "type": t["type"], "family": t.get("family", "unclassified")}
        turns = t["turns"] if t["type"] == "multiturn" else [t]
        try:
            msgs = [{"role": "system", "content": system}]
            turn_rows = []
            task_score, task_mode = 1.0, "ok"
            for ti, turn in enumerate(turns):
                q = turn["question"]
                msgs.append({"role": "user",
                             "content": doc + "\n\nQuestion: " + q} if ti == 0
                            else {"role": "user", "content": q})
                cap, tok_est = gen_cap(args.endpoint, args.model, msgs)
                try:
                    text, usage, ms = chat(args.endpoint, args.model, msgs, cap)
                except Exception as e:
                    # Per-turn error: keep completed turns, stop this task.
                    # (v2.0 lost the whole task here, e.g. multiturn history
                    # overflow when a rambling turn-1 reply pushed the prompt
                    # over the cap.)
                    turn_rows.append({"turn": ti + 1, "score": 0.0, "mode": "error",
                                      "error": str(e)[:300], "max_tokens": cap,
                                      "tokenize_estimate": tok_est})
                    if task_score == 1.0:
                        task_mode = "error"
                    task_score = 0.0
                    break
                sc, mode, diag = score_turn(turn, text)
                tr = {"turn": ti + 1, "score": sc, "mode": mode,
                      "prompt_tokens": usage.get("prompt_tokens"),
                      "tokenize_estimate": tok_est, "max_tokens": cap,
                      "latency_ms": round(ms, 1),
                      "response": text[:1000]}
                tr.update(diag)
                turn_rows.append(tr)
                # Truncate echoed/rambling replies in history so a long turn-1
                # cannot push a later turn's prompt over the 102400 cap.
                # Genuine answers are far shorter than 1000 chars; unaffected.
                msgs.append({"role": "assistant", "content": text[:1000]})
                if sc < 1.0 and task_score == 1.0:
                    task_mode = mode
                task_score = task_score if sc == 1.0 else 0.0
            row["turns"] = turn_rows
            row["score"] = task_score
            row["failure_mode"] = task_mode if task_score < 1.0 else "ok"
            row["prompt_tokens"] = turn_rows[-1]["prompt_tokens"]
            row["latency_ms"] = turn_rows[-1]["latency_ms"]
        except Exception as e:
            row.update({"score": 0.0, "failure_mode": "error",
                        "error": str(e)[:300]})
            failures.append({"id": t["id"], "mode": "error",
                             "error": str(e)[:200]})
            rows.append(row)
            n += 1
            continue
        if row["score"] < 1.0:
            failures.append({"id": t["id"], "mode": row["failure_mode"],
                             "turn_scores": [tr["score"] for tr in row["turns"]]})
        total += row["score"]
        n += 1
        rows.append(row)

    fams = {}
    for r in rows:
        f = r.get("family", "unclassified")
        fams.setdefault(f, {"n": 0, "passed": 0})
        fams[f]["n"] += 1
        if r.get("score", 0.0) == 1.0:
            fams[f]["passed"] += 1
    for f in fams:
        fams[f]["score"] = round(fams[f]["passed"] / fams[f]["n"], 4)
    out = {"model": args.model, "endpoint": args.endpoint, "suite": "longhorizon-v2r",
           "families": fams,
           "n_tasks": len(tasks), "n_scored": n,
           "overall_score": round(total / n, 4) if n else None,
           "n_failures": len(failures), "failures": failures, "rows": rows}
    json.dump(out, open(args.out, "w"), indent=2)
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()
