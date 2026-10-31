#!/usr/bin/env python3
"""OCR bench runner: POST image+question to /v1/chat/completions, temp 0.
Scoring (deterministic, substring, case-insensitive):
- extract: field fraction = fields present / fields total; note content present = contamination flag.
- refuse: pass iff a refusal phrase is present AND no forbidden value is present;
  forbidden value present = HALLUCINATION failure.
- redacted: visible fields fraction + total-refusal bit (no forbidden value as total).
- leftcol: pass iff field present AND forbidden absent.
Usage: python3 ocr-bench.py --endpoint http://127.0.0.1:8080/v1 --model ID --tasks tasks.json --images dir --out results.json
"""
import argparse, base64, json, os, time, urllib.request

REFUSAL_DEFAULT = ["illegible", "cannot read", "can't read", "unreadable", "too blurry", "not legible"]


def post(endpoint, model, image_path, question):
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": question},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]}],
        "temperature": 0.0, "max_tokens": 512,
    }).encode()
    req = urllib.request.Request(endpoint + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=300) as r:
        resp = json.load(r)
    return resp["choices"][0]["message"]["content"] or "", (time.perf_counter() - t0) * 1000.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--images", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    tasks = json.load(open(args.tasks))["tasks"]
    rows, failures = [], []
    total_score, n = 0.0, 0
    for t in tasks:
        try:
            text, ms = post(args.endpoint, args.model,
                            os.path.join(args.images, t["image"]), t["question"])
        except Exception as e:
            failures.append({"id": t["id"], "error": str(e)})
            rows.append({"id": t["id"], "type": t["type"], "error": str(e)})
            continue
        low = text.lower()
        row = {"id": t["id"], "type": t["type"], "latency_ms": round(ms, 1),
               "response": text[:500]}
        if t["type"] == "extract":
            present = [f for f in t["fields"] if f.lower() in low]
            score = len(present) / len(t["fields"])
            row.update({"fields_present": present, "score": round(score, 4)})
            if "exclude_values" in t:
                contam = [v for v in t["exclude_values"] if v.lower() in low]
                row["contamination"] = contam
                if contam:
                    failures.append({"id": t["id"], "failure": "contamination", "values": contam})
            if score < 1.0 and not any(p in low for p in REFUSAL_DEFAULT):
                row["failure_mode"] = "missed_fields"
            elif score < 1.0:
                row["failure_mode"] = "safe_refusal"
        elif t["type"] == "refuse":
            phrases = t.get("refusal_phrases", REFUSAL_DEFAULT)
            refused = any(p.lower() in low for p in phrases)
            hallu = [v for v in t["forbidden_values"] if v.lower() in low]
            score = 1.0 if (refused and not hallu) else 0.0
            row.update({"refused": refused, "hallucinated_values": hallu, "score": score})
            if hallu:
                failures.append({"id": t["id"], "failure": "HALLUCINATION", "values": hallu})
            elif not refused:
                failures.append({"id": t["id"], "failure": "accepted_illegible"})
        elif t["type"] == "redacted":
            present = [f for f in t["fields"] if f.lower() in low]
            phrases = t.get("refusal_phrases", REFUSAL_DEFAULT)
            refused_total = any(p.lower() in low for p in phrases)
            hallu = [v for v in t["forbidden_values"] if v.lower() in low]
            score = (len(present) / len(t["fields"]) + (1.0 if (refused_total and not hallu) else 0.0)) / 2.0
            row.update({"fields_present": present, "refused_total": refused_total,
                        "hallucinated_values": hallu, "score": round(score, 4)})
            if hallu:
                failures.append({"id": t["id"], "failure": "HALLUCINATION", "values": hallu})
        elif t["type"] == "leftcol":
            ok = t["fields"][0].lower() in low and not any(
                v.lower() in low for v in t["forbidden_values"])
            score = 1.0 if ok else 0.0
            row.update({"score": score})
            if not ok:
                failures.append({"id": t["id"], "failure": "layout_constraint_failed"})
        total_score += row["score"]
        n += 1
        rows.append(row)

    out = {"model": args.model, "endpoint": args.endpoint,
           "n_tasks": len(tasks), "n_scored": n,
           "overall_field_score": round(total_score / n, 4) if n else None,
           "n_failures": len(failures), "failures": failures, "rows": rows}
    json.dump(out, open(args.out, "w"), indent=2)
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()
