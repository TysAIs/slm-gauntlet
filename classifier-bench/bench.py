#!/usr/bin/env python3
"""Classifier benchmark runner for /v1/systemone decision models.
Usage: python3 classifier-bench.py --endpoint http://127.0.0.1:8080/v1 --model MODEL_ID --tasks tasks.json --out results.json
Metrics: choice accuracy, noul accuracy @0.5, score exact-level accuracy + MAE,
ECE (10 bins, choice max-prob vs correctness), multiclass Brier (choice),
mean/p95 latency ms, abstention rate (confidence < 0.6), option-order flip rate (choice).
Deterministic: fixed task order, fixed shuffled order (reversed options).
"""
import argparse, json, statistics, sys, time, urllib.request


def post(endpoint, state, questions):
    body = json.dumps({"state": state, "questions": questions}).encode()
    req = urllib.request.Request(endpoint + "/systemone", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.load(r)
    return resp, (time.perf_counter() - t0) * 1000.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    tasks = json.load(open(args.tasks))["tasks"]
    rows, latencies, failures = [], [], []
    choice_correct, choice_conf, choice_brier = [], [], []
    noul_correct, score_exact, score_abs_err = [], [], []
    abstain, total = 0, 0
    flips, choice_total = 0, 0

    for t in tasks:
        qid = t["id"]
        if t["type"] == "choice":
            q = {"type": "choice", "instructions": t["instructions"],
                 "criteria": t["options"]}
        elif t["type"] == "score":
            q = {"type": "score", "instructions": t["instructions"],
                 "criteria": t["options"]}
        else:
            q = {"type": "noul", "instructions": t["instructions"]}
        try:
            resp, ms = post(args.endpoint, t["state"], {qid: q})
            ans = resp["answers"][qid]
        except Exception as e:
            failures.append({"id": qid, "error": str(e)})
            continue
        latencies.append(ms)
        total += 1
        row = {"id": qid, "type": t["type"], "truth": t["truth"], "latency_ms": round(ms, 1)}
        if t["type"] == "choice":
            choice_total += 1
            pred = ans["choice"]
            probs = ans["probabilities"]
            correct = int(pred == t["truth"])
            choice_correct.append(correct)
            conf = ans.get("confidence", max(probs.values()))
            choice_conf.append(conf)
            brier = sum((probs.get(k, 0.0) - (1.0 if k == t["truth"] else 0.0)) ** 2
                        for k in probs)
            choice_brier.append(brier)
            if conf < 0.6:
                abstain += 1
            row.update({"pred": pred, "correct": correct, "confidence": round(conf, 4),
                        "p_truth": round(probs.get(t["truth"], 0.0), 4)})
            # order sensitivity: reversed option order, same state
            rev_opts = dict(reversed(list(t["options"].items())))
            q2 = {"type": "choice", "instructions": t["instructions"], "criteria": rev_opts}
            try:
                resp2, _ = post(args.endpoint, t["state"], {qid: q2})
                pred2 = resp2["answers"][qid]["choice"]
                if pred2 != pred:
                    flips += 1
                row["pred_reversed_order"] = pred2
            except Exception as e:
                failures.append({"id": qid + "-reversed", "error": str(e)})
        elif t["type"] == "noul":
            p = ans["noul"]
            pred = p >= 0.5
            correct = int(pred == t["truth"])
            noul_correct.append(correct)
            conf = max(p, 1.0 - p)
            if conf < 0.6:
                abstain += 1
            row.update({"pred": pred, "p": round(p, 4), "correct": correct,
                        "confidence": round(conf, 4)})
        else:
            pred_score = ans["score"]
            # score is expected value; exact-level = nearest level
            pred_level = int(round(pred_score))
            exact = int(pred_level == t["truth"])
            score_exact.append(exact)
            score_abs_err.append(abs(pred_score - t["truth"]))
            conf = ans.get("confidence", 0.0)
            if conf < 0.6:
                abstain += 1
            row.update({"pred_score": round(pred_score, 4), "pred_level": pred_level,
                        "exact": exact, "abs_err": round(abs(pred_score - t["truth"]), 4),
                        "confidence": round(conf, 4)})
        rows.append(row)

    # ECE on choice tasks: 10 equal-width confidence bins
    ece = 0.0
    if choice_conf:
        for b in range(10):
            lo, hi = b / 10.0, (b + 1) / 10.0
            idx = [i for i, c in enumerate(choice_conf) if lo <= c < hi or (b == 9 and c == 1.0)]
            if idx:
                acc = sum(choice_correct[i] for i in idx) / len(idx)
                conf = sum(choice_conf[i] for i in idx) / len(idx)
                ece += abs(acc - conf) * len(idx) / len(choice_conf)

    lat_sorted = sorted(latencies)
    p95 = lat_sorted[int(0.95 * (len(lat_sorted) - 1))] if lat_sorted else 0.0
    out = {
        "model": args.model, "endpoint": args.endpoint,
        "n_tasks": len(tasks), "n_scored": total, "n_failures": len(failures),
        "choice_accuracy": round(sum(choice_correct) / len(choice_correct), 4) if choice_correct else None,
        "choice_n": len(choice_correct),
        "noul_accuracy": round(sum(noul_correct) / len(noul_correct), 4) if noul_correct else None,
        "noul_n": len(noul_correct),
        "score_exact_accuracy": round(sum(score_exact) / len(score_exact), 4) if score_exact else None,
        "score_mae": round(sum(score_abs_err) / len(score_abs_err), 4) if score_abs_err else None,
        "score_n": len(score_exact),
        "ece_choice": round(ece, 4),
        "brier_choice": round(sum(choice_brier) / len(choice_brier), 4) if choice_brier else None,
        "latency_mean_ms": round(statistics.mean(latencies), 1) if latencies else None,
        "latency_p95_ms": round(p95, 1),
        "abstention_rate_conf_lt_0.6": round(abstain / total, 4) if total else None,
        "order_flip_rate_choice": round(flips / choice_total, 4) if choice_total else None,
        "order_flips": flips, "choice_n_order": choice_total,
        "failures": failures, "rows": rows,
    }
    json.dump(out, open(args.out, "w"), indent=2)
    print(json.dumps({k: v for k, v in out.items() if k not in ("rows", "failures")}, indent=2))


if __name__ == "__main__":
    main()
