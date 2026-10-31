#!/usr/bin/env python3
"""Long-horizon 100K+ bench: shared long document + 8 tasks, temp 0.
One POST per task (doc + question); multi-turn task does 2 sequential calls
with history. Scoring is deterministic: numeric normalization ($ and commas
stripped), field substring, exact ISO date. Records usage.prompt_tokens per
task (the honest per-model token count for the same document).
Usage: python3 lh-bench.py --endpoint ... --model ID --doc doc.txt --tasks tasks.json --out results.json
"""
import argparse, json, re, time, urllib.request


def chat(endpoint, model, messages, max_tokens=4096):
    body = json.dumps({"model": model, "messages": messages,
                       "temperature": 0.0, "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(endpoint + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=1800) as r:
        resp = json.load(r)
    ms = (time.perf_counter() - t0) * 1000.0
    ch = resp["choices"][0]["message"]
    return (ch.get("content") or ""), resp.get("usage", {}), ms


def norm_num(text):
    m = re.findall(r"\$?\s*([\d,]+(?:\.\d+)?)", text or "")
    vals = set()
    for v in m:
        try:
            vals.add(float(v.replace(",", "")))
        except ValueError:
            pass
    return vals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--doc", required=True)
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    doc = open(args.doc).read()
    tasks = json.load(open(args.tasks))["tasks"]
    system = ("You are a careful analyst. Answer ONLY from the document provided. "
              "Follow the reporting policies stated at the start of the document.")
    rows, failures = [], []
    total, n = 0.0, 0
    for t in tasks:
        row = {"id": t["id"], "type": t["type"]}
        try:
            if t["type"] == "multiturn":
                msgs = [{"role": "system", "content": system},
                        {"role": "user", "content": doc + "\n\nQuestion: " + t["turn1"]}]
                a1, u1, ms1 = chat(args.endpoint, args.model, msgs)
                msgs.append({"role": "assistant", "content": a1})
                msgs.append({"role": "user", "content": t["turn2"]})
                text, usage, ms = chat(args.endpoint, args.model, msgs)
                row.update({"turn1_response": a1[:300], "turn1_prompt_tokens": u1.get("prompt_tokens"),
                            "turn1_answer_present": float(t["turn1_answer"]) in norm_num(a1)})
                prompt_tokens = usage.get("prompt_tokens")
            else:
                msgs = [{"role": "system", "content": system},
                        {"role": "user", "content": doc + "\n\nQuestion: " + t["question"]}]
                text, usage, ms = chat(args.endpoint, args.model, msgs)
                prompt_tokens = usage.get("prompt_tokens")
        except Exception as e:
            row.update({"error": str(e)})
            failures.append({"id": t["id"], "error": str(e)})
            rows.append(row)
            continue
        row.update({"latency_ms": round(ms, 1), "prompt_tokens": prompt_tokens,
                    "response": text[:500]})
        if t["type"] in ("numeric", "multiturn"):
            score = 1.0 if float(t["answer"]) in norm_num(text) else 0.0
        elif t["type"] == "fields":
            present = [f for f in t["fields"] if f.lower() in text.lower()]
            score = len(present) / len(t["fields"])
            row["fields_present"] = present
        elif t["type"] == "exact":
            score = 1.0 if t["answer"] in text else 0.0
        else:
            score = 0.0
        row["score"] = score
        if score < 1.0:
            failures.append({"id": t["id"], "score": score,
                             "response_head": text[:200]})
        total += score
        n += 1
        rows.append(row)

    out = {"model": args.model, "endpoint": args.endpoint,
           "n_tasks": len(tasks), "n_scored": n,
           "overall_score": round(total / n, 4) if n else None,
           "n_failures": len(failures), "failures": failures, "rows": rows}
    json.dump(out, open(args.out, "w"), indent=2)
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()
