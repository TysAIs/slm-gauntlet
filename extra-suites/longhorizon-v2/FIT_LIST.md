# Long-horizon v2 — 102400 FIT LIST (from run log, parsed mechanically)

Source: ~/workspace/research/slm-gauntlet-pve-run-2026-10-27.md (AREO repo run log),
context-push + LH-serve records. Parsed by section header (family/quant/KV) + the
`102400 serve ... VRAM x MiB, spare y MiB` line in that section. Summary lines with no
VRAM were ignored. One misattribution was corrected by hand: Dory q8_0 at 102400 FAILED
(KV alloc OOM); the 6785 MiB figure on that log line is the 45056 serve, NOT 102400.
Rule (parent directive): FIT = serve at 102400 with VRAM spare >= 1024 MiB. FLAGGED =
served but spare < 1024 MiB (sweep-excluded at that KV; a q4_0-KV sibling may rescue it).
FAIL = could not serve at 102400 at all. VRAM was measured on the build in use at the
time (old Sep-11 build for early pushes, new dory-merge build for expanded pushes and all
Oct-31 LH serves); the sweep executor MUST re-verify spare >= 1024 MiB at each serve,
because the new build may shift VRAM by tens of MiB.

## Counts (quant x KV records with a 102400 measurement)
- FIT by VRAM: 206
- FLAGGED (served, spare < 1024): 4
- FAIL at 102400: 2
- Total measured keys: 212
- Sweep-eligible by VRAM + model caps (see exclusions below): 184
  (206 VRAM-FIT keys minus 24 Bolt model-cap exclusions minus 1 gated Dory q4_0,
  plus 3 LH-only keys: Qwen3.5-9B Q4_K_M q4_0, LFM2.5-1.2B Q8_0 FP16, LFM2.5-8B UD-Q4_K_M FP16.)

## Model-level exclusions (VRAM fit does NOT make these sweep-eligible)
- ALL Bolt E4B variants (24 keys): server log caps context at 65536 (training context).
  v1 LH prompt (93,154 tokens on Bolt tokenization) exceeded the cap with clean HTTP 400.
  Bolt is does-not-fit at 100K+ as a MODEL, not per-quant. No Bolt LH serve is needed.
- Dory 1.0 4B Q5_K_M q4_0: VRAM FIT (6909/1283) but v1 LH prompt was 103,328-103,346 tokens
  on Dory tokenization, OVER the 102400 cap (clean HTTP 400 on all 8 v1 tasks). GATE for v2:
  the v2 doc is ~690 words shorter, so the v2 prompt may land just under the cap; the sweep
  executor must read task-1 prompt_tokens first: if prompt + 256 > 102400, record Dory as
  does-not-fit for v2 and move on. Do not assume fit or failure.
- Dory Q5_K_M q8_0: FAIL at 102400 (KV alloc OOM); max measured serve 45056. Excluded.

## Not proven at 102400 (no record in the run log — fit-test BEFORE any sweep scoring)
- LFM2.5-1.2B Q4_K_M, all KVs (only Q8_0 FP16 was LH-served: 2673/5519 FIT).
- LFM2.5-8B-A1B UD-Q4_K_M, q8_0 / q4_0 KV (only FP16 LH-served: 6549/1643 FIT; Q8_0 file
  exceeds VRAM alone and was never downloaded for on-GPU serve).
- Bolt E4B UD-Q8_K_XL, all KVs (32K served, 5891 MiB; no 102400 record). Moot: Bolt is
  model-excluded by the 65536 cap anyway.
- Qwen3.5-9B Q4_K_M FP16 (FAIL at 102400, KV alloc OOM) and q8_0 KV (never served at 102400).
  Only q4_0 KV is FIT (6847/1345).
- All v0.3.1-era variants (Gemma 4 E4B/12B, Gemma 3n, LFM2.5-2.6B, MiniCPM-V 5 2B, MiMo 9B,
  Ornith 9B, Qwen3.5-4B, Sharp-Spark 4B, Spark-X2.5, Llama-3.1-8B, Bonsai-2, K2-Horizon 7B):
  skipped as already-tested in this run; no 102400 record exists. Excluded from this sweep
  unless fit-tested separately. Out of scope, not does-not-fit.
- Offload lane (LFM2.5-24B-A2B, Flint): separate lane, not on-GPU sweep candidates.
- Classifier models, LFM3-VL-2B (vision/OCR track), Granite Switch (no GGUF): not LH candidates.

## LH-only additions (measured in Oct-31 LH serves, not in quant context-push sections)
| Family | Quant | KV | VRAM (MiB) | Spare (MiB) | Verdict |
|---|---|---|---|---|---|
| Qwen3.5-9B | Q4_K_M | q4_0 | 6847 | 1345 | FIT |
| Qwen3.5-9B | Q4_K_M | FP16 | - | - | FAIL (KV alloc OOM) |
| LFM2.5-1.2B | Q8_0 | FP16 | 2673 | 5519 | FIT |
| LFM2.5-8B-A1B | UD-Q4_K_M | FP16 | 6549 | 1643 | FIT |
| Spark-X2.6-4B | IQ3_M (bartowski) | FP16 | 6519 | 1673 | FIT (also in table below) |
| Spark-X2.6-1.7B | Q8_0 | FP16 | 3599 | 4593 | FIT (context-push record 3595/4597; 4 MiB measurement difference) |
| MiniCPM-V 4.7 1B | IQ4_XS | FP16 | 2103 | 6089 | FIT (also in table below) |
| LFM3-1.7B | IQ4_NL (bartowski) | FP16 | 2571 | 5621 | FIT (also in table below) |

## Full table (VRAM at 102400 serve; 8192 MiB total)
| Family | Quant | Source | KV | VRAM | Spare | Verdict |
|---|---|---|---|---|---|---|
| Bolt E4B | Q4_K_M | nvidia official | FP16 | 5127 | 3065 | FIT |
| Bolt E4B | Q4_K_M | nvidia official | q4_0 | 4219 | 3973 | FIT |
| Bolt E4B | Q4_K_M | nvidia official | q8_0 | 4663 | 3529 | FIT |
| Bolt E4B | UD-IQ2_M | official | FP16 | 3971 | 4221 | FIT |
| Bolt E4B | UD-IQ2_M | official | q4_0 | 3043 | 5149 | FIT |
| Bolt E4B | UD-IQ2_M | official | q8_0 | 3487 | 4705 | FIT |
| Bolt E4B | UD-IQ3_XXS | official | FP16 | 4135 | 4057 | FIT |
| Bolt E4B | UD-IQ3_XXS | official | q4_0 | 3207 | 4985 | FIT |
| Bolt E4B | UD-IQ3_XXS | official | q8_0 | 3651 | 4541 | FIT |
| Bolt E4B | UD-Q2_K_XL | official | FP16 | 4171 | 4021 | FIT |
| Bolt E4B | UD-Q2_K_XL | official | q4_0 | 3243 | 4949 | FIT |
| Bolt E4B | UD-Q2_K_XL | official | q8_0 | 3687 | 4505 | FIT |
| Bolt E4B | UD-Q3_K_XL | official | FP16 | 4627 | 3565 | FIT |
| Bolt E4B | UD-Q3_K_XL | official | q4_0 | 3699 | 4493 | FIT |
| Bolt E4B | UD-Q3_K_XL | official | q8_0 | 4143 | 4049 | FIT |
| Bolt E4B | UD-Q4_K_XL | official | FP16 | 5403 | 2789 | FIT |
| Bolt E4B | UD-Q4_K_XL | official | q4_0 | 4495 | 3697 | FIT |
| Bolt E4B | UD-Q4_K_XL | official | q8_0 | 4939 | 3253 | FIT |
| Bolt E4B | UD-Q5_K_XL | official | FP16 | 5803 | 2389 | FIT |
| Bolt E4B | UD-Q5_K_XL | official | q4_0 | 4895 | 3297 | FIT |
| Bolt E4B | UD-Q5_K_XL | official | q8_0 | 5339 | 2853 | FIT |
| Bolt E4B | UD-Q6_K_XL | official | FP16 | 6807 | 1385 | FIT |
| Bolt E4B | UD-Q6_K_XL | official | q4_0 | 5899 | 2293 | FIT |
| Bolt E4B | UD-Q6_K_XL | official | q8_0 | 6343 | 1849 | FIT |
| Dory 1.0 4B | Q5_K_M | official | q4_0 | 6909 | 1283 | FIT |
| Dory 1.0 4B | Q5_K_M | official | q8_0 | - | - | FAIL @102400 |
| LFM3-1.7B | IQ2_M | bartowski | FP16 | 2127 | 6065 | FIT |
| LFM3-1.7B | IQ2_M | bartowski | q4_0 | 1411 | 6781 | FIT |
| LFM3-1.7B | IQ2_M | bartowski | q8_0 | 1717 | 6475 | FIT |
| LFM3-1.7B | IQ3_M | bartowski | FP16 | 2389 | 5803 | FIT |
| LFM3-1.7B | IQ3_M | bartowski | q4_0 | 1673 | 6519 | FIT |
| LFM3-1.7B | IQ3_M | bartowski | q8_0 | 1979 | 6213 | FIT |
| LFM3-1.7B | IQ3_XS | bartowski | FP16 | 2281 | 5911 | FIT |
| LFM3-1.7B | IQ3_XS | bartowski | q4_0 | 1565 | 6627 | FIT |
| LFM3-1.7B | IQ3_XS | bartowski | q8_0 | 1871 | 6321 | FIT |
| LFM3-1.7B | IQ3_XXS | bartowski | FP16 | 2251 | 5941 | FIT |
| LFM3-1.7B | IQ3_XXS | bartowski | q4_0 | 1535 | 6657 | FIT |
| LFM3-1.7B | IQ3_XXS | bartowski | q8_0 | 1841 | 6351 | FIT |
| LFM3-1.7B | IQ4_NL | bartowski | FP16 | 2571 | 5621 | FIT |
| LFM3-1.7B | IQ4_NL | bartowski | q4_0 | 1855 | 6337 | FIT |
| LFM3-1.7B | IQ4_NL | bartowski | q8_0 | 2161 | 6031 | FIT |
| LFM3-1.7B | IQ4_XS | bartowski | FP16 | 2457 | 5735 | FIT |
| LFM3-1.7B | IQ4_XS | bartowski | q4_0 | 1741 | 6451 | FIT |
| LFM3-1.7B | IQ4_XS | bartowski | q8_0 | 2047 | 6145 | FIT |
| LFM3-1.7B | Q2_K | bartowski | FP16 | 2175 | 6017 | FIT |
| LFM3-1.7B | Q2_K | bartowski | q4_0 | 1459 | 6733 | FIT |
| LFM3-1.7B | Q2_K | bartowski | q8_0 | 1765 | 6427 | FIT |
| LFM3-1.7B | Q3_K_L | prithiv | FP16 | 2429 | 5763 | FIT |
| LFM3-1.7B | Q3_K_L | prithiv | q4_0 | 1713 | 6479 | FIT |
| LFM3-1.7B | Q3_K_L | prithiv | q8_0 | 2019 | 6173 | FIT |
| LFM3-1.7B | Q3_K_M | prithiv | FP16 | 2379 | 5813 | FIT |
| LFM3-1.7B | Q3_K_M | prithiv | q4_0 | 1663 | 6529 | FIT |
| LFM3-1.7B | Q3_K_M | prithiv | q8_0 | 1969 | 6223 | FIT |
| LFM3-1.7B | Q3_K_S | bartowski | FP16 | 2281 | 5911 | FIT |
| LFM3-1.7B | Q3_K_S | bartowski | q4_0 | 1565 | 6627 | FIT |
| LFM3-1.7B | Q3_K_S | bartowski | q8_0 | 1871 | 6321 | FIT |
| LFM3-1.7B | Q4_0 | bartowski | FP16 | 2515 | 5677 | FIT |
| LFM3-1.7B | Q4_0 | bartowski | q4_0 | 1799 | 6393 | FIT |
| LFM3-1.7B | Q4_0 | bartowski | q8_0 | 2105 | 6087 | FIT |
| LFM3-1.7B | Q4_1 | bartowski | FP16 | 2599 | 5593 | FIT |
| LFM3-1.7B | Q4_1 | bartowski | q4_0 | 1883 | 6309 | FIT |
| LFM3-1.7B | Q4_1 | bartowski | q8_0 | 2189 | 6003 | FIT |
| LFM3-1.7B | Q4_K_M | official | q4_0 | 1839 | 6353 | FIT |
| LFM3-1.7B | Q4_K_M | official | q8_0 | 2145 | 6047 | FIT |
| LFM3-1.7B | Q4_K_M | LiquidAI | FP16 | 2555 | 5637 | FIT |
| LFM3-1.7B | Q4_K_S | prithiv | FP16 | 2513 | 5679 | FIT |
| LFM3-1.7B | Q4_K_S | prithiv | q4_0 | 1797 | 6395 | FIT |
| LFM3-1.7B | Q4_K_S | prithiv | q8_0 | 2103 | 6089 | FIT |
| LFM3-1.7B | Q5_K_M | official | FP16 | 2707 | 5485 | FIT |
| LFM3-1.7B | Q5_K_M | official | q4_0 | 1991 | 6201 | FIT |
| LFM3-1.7B | Q5_K_M | official | q8_0 | 2297 | 5895 | FIT |
| LFM3-1.7B | Q5_K_S | prithiv | FP16 | 2681 | 5511 | FIT |
| LFM3-1.7B | Q5_K_S | prithiv | q4_0 | 1965 | 6227 | FIT |
| LFM3-1.7B | Q5_K_S | prithiv | q8_0 | 2271 | 5921 | FIT |
| LFM3-1.7B | Q6_K | official | FP16 | 2867 | 5325 | FIT |
| LFM3-1.7B | Q6_K | official | q4_0 | 2151 | 6041 | FIT |
| LFM3-1.7B | Q6_K | official | q8_0 | 2457 | 5735 | FIT |
| LFM3-1.7B | Q6_K_L | bartowski | FP16 | 3015 | 5177 | FIT |
| LFM3-1.7B | Q6_K_L | bartowski | q4_0 | 2299 | 5893 | FIT |
| LFM3-1.7B | Q6_K_L | bartowski | q8_0 | 2605 | 5587 | FIT |
| LFM3-1.7B | Q6_K_S | bartowski | FP16 | 2895 | 5297 | FIT |
| LFM3-1.7B | Q6_K_S | bartowski | q4_0 | 2179 | 6013 | FIT |
| LFM3-1.7B | Q6_K_S | bartowski | q8_0 | 2485 | 5707 | FIT |
| LFM3-1.7B | Q8_0 | official | FP16 | 3267 | 4925 | FIT |
| LFM3-1.7B | Q8_0 | official | q4_0 | 2551 | 5641 | FIT |
| LFM3-1.7B | Q8_0 | official | q8_0 | 2857 | 5335 | FIT |
| MiniCPM-V 4.7 1B | IQ3_M | openbmb | FP16 | 2055 | 6137 | FIT |
| MiniCPM-V 4.7 1B | IQ3_M | openbmb | q4_0 | 1365 | 6827 | FIT |
| MiniCPM-V 4.7 1B | IQ3_M | openbmb | q8_0 | 1665 | 6527 | FIT |
| MiniCPM-V 4.7 1B | IQ3_XS | openbmb | FP16 | 2045 | 6147 | FIT |
| MiniCPM-V 4.7 1B | IQ3_XS | openbmb | q4_0 | 1355 | 6837 | FIT |
| MiniCPM-V 4.7 1B | IQ3_XS | openbmb | q8_0 | 1655 | 6537 | FIT |
| MiniCPM-V 4.7 1B | IQ4_NL | openbmb | FP16 | 2113 | 6079 | FIT |
| MiniCPM-V 4.7 1B | IQ4_NL | openbmb | q4_0 | 1423 | 6769 | FIT |
| MiniCPM-V 4.7 1B | IQ4_NL | openbmb | q8_0 | 1723 | 6469 | FIT |
| MiniCPM-V 4.7 1B | IQ4_XS | openbmb | FP16 | 2103 | 6089 | FIT |
| MiniCPM-V 4.7 1B | IQ4_XS | openbmb | q4_0 | 1413 | 6779 | FIT |
| MiniCPM-V 4.7 1B | IQ4_XS | openbmb | q8_0 | 1713 | 6479 | FIT |
| MiniCPM-V 4.7 1B | Q4_0 | openbmb | FP16 | 2099 | 6093 | FIT |
| MiniCPM-V 4.7 1B | Q4_0 | openbmb | q4_0 | 1409 | 6783 | FIT |
| MiniCPM-V 4.7 1B | Q4_0 | openbmb | q8_0 | 1709 | 6483 | FIT |
| MiniCPM-V 4.7 1B | Q4_1 | openbmb | FP16 | 2129 | 6063 | FIT |
| MiniCPM-V 4.7 1B | Q4_1 | openbmb | q4_0 | 1439 | 6753 | FIT |
| MiniCPM-V 4.7 1B | Q4_1 | openbmb | q8_0 | 1739 | 6453 | FIT |
| MiniCPM-V 4.7 1B | Q4_K_M | official | FP16 | 2123 | 6069 | FIT |
| MiniCPM-V 4.7 1B | Q4_K_M | official | q4_0 | 1433 | 6759 | FIT |
| MiniCPM-V 4.7 1B | Q4_K_M | official | q8_0 | 1733 | 6459 | FIT |
| MiniCPM-V 4.7 1B | Q4_K_S | openbmb | FP16 | 2103 | 6089 | FIT |
| MiniCPM-V 4.7 1B | Q4_K_S | openbmb | q4_0 | 1413 | 6779 | FIT |
| MiniCPM-V 4.7 1B | Q4_K_S | openbmb | q8_0 | 1713 | 6479 | FIT |
| MiniCPM-V 4.7 1B | Q5_0 | openbmb | FP16 | 2159 | 6033 | FIT |
| MiniCPM-V 4.7 1B | Q5_0 | openbmb | q4_0 | 1469 | 6723 | FIT |
| MiniCPM-V 4.7 1B | Q5_0 | openbmb | q8_0 | 1769 | 6423 | FIT |
| MiniCPM-V 4.7 1B | Q5_1 | openbmb | FP16 | 2189 | 6003 | FIT |
| MiniCPM-V 4.7 1B | Q5_1 | openbmb | q4_0 | 1499 | 6693 | FIT |
| MiniCPM-V 4.7 1B | Q5_1 | openbmb | q8_0 | 1799 | 6393 | FIT |
| MiniCPM-V 4.7 1B | Q5_K_M | official | FP16 | 2169 | 6023 | FIT |
| MiniCPM-V 4.7 1B | Q5_K_M | official | q4_0 | 1479 | 6713 | FIT |
| MiniCPM-V 4.7 1B | Q5_K_M | official | q8_0 | 1779 | 6413 | FIT |
| MiniCPM-V 4.7 1B | Q5_K_S | openbmb | FP16 | 2159 | 6033 | FIT |
| MiniCPM-V 4.7 1B | Q5_K_S | openbmb | q4_0 | 1469 | 6723 | FIT |
| MiniCPM-V 4.7 1B | Q5_K_S | openbmb | q8_0 | 1769 | 6423 | FIT |
| MiniCPM-V 4.7 1B | Q6_K | official | FP16 | 2217 | 5975 | FIT |
| MiniCPM-V 4.7 1B | Q6_K | official | q4_0 | 1527 | 6665 | FIT |
| MiniCPM-V 4.7 1B | Q6_K | official | q8_0 | 1827 | 6365 | FIT |
| MiniCPM-V 4.7 1B | Q8_0 | official | FP16 | 2391 | 5801 | FIT |
| MiniCPM-V 4.7 1B | Q8_0 | official | q4_0 | 1701 | 6491 | FIT |
| MiniCPM-V 4.7 1B | Q8_0 | official | q8_0 | 2001 | 6191 | FIT |
| Spark-X2.6-1.7B | Q3_K_L | XHToken | FP16 | 2835 | 5357 | FIT |
| Spark-X2.6-1.7B | Q3_K_L | XHToken | q4_0 | 1869 | 6323 | FIT |
| Spark-X2.6-1.7B | Q3_K_L | XHToken | q8_0 | 2267 | 5925 | FIT |
| Spark-X2.6-1.7B | Q3_K_M | XHToken | FP16 | 2757 | 5435 | FIT |
| Spark-X2.6-1.7B | Q3_K_M | XHToken | q4_0 | 1791 | 6401 | FIT |
| Spark-X2.6-1.7B | Q3_K_M | XHToken | q8_0 | 2189 | 6003 | FIT |
| Spark-X2.6-1.7B | Q4_K_M | official | FP16 | 3033 | 5159 | FIT |
| Spark-X2.6-1.7B | Q4_K_M | official | q4_0 | 2067 | 6125 | FIT |
| Spark-X2.6-1.7B | Q4_K_M | official | q8_0 | 2465 | 5727 | FIT |
| Spark-X2.6-1.7B | Q4_K_S | XHToken | FP16 | 2859 | 5333 | FIT |
| Spark-X2.6-1.7B | Q4_K_S | XHToken | q4_0 | 1893 | 6299 | FIT |
| Spark-X2.6-1.7B | Q4_K_S | XHToken | q8_0 | 2291 | 5901 | FIT |
| Spark-X2.6-1.7B | Q5_K_S | XHToken | FP16 | 3021 | 5171 | FIT |
| Spark-X2.6-1.7B | Q5_K_S | XHToken | q4_0 | 2055 | 6137 | FIT |
| Spark-X2.6-1.7B | Q5_K_S | XHToken | q8_0 | 2453 | 5739 | FIT |
| Spark-X2.6-1.7B | Q6_K | XHToken | FP16 | 3205 | 4987 | FIT |
| Spark-X2.6-1.7B | Q6_K | XHToken | q4_0 | 2239 | 5953 | FIT |
| Spark-X2.6-1.7B | Q6_K | XHToken | q8_0 | 2637 | 5555 | FIT |
| Spark-X2.6-1.7B | Q8_0 | official | FP16 | 3595 | 4597 | FIT |
| Spark-X2.6-1.7B | Q8_0 | official | q4_0 | 2629 | 5563 | FIT |
| Spark-X2.6-1.7B | Q8_0 | official | q8_0 | 3027 | 5165 | FIT |
| Spark-X2.6-4B | IQ2_M | bartowski | FP16 | 5883 | 2309 | FIT |
| Spark-X2.6-4B | IQ2_M | bartowski | q4_0 | 3321 | 4871 | FIT |
| Spark-X2.6-4B | IQ2_M | bartowski | q8_0 | 4343 | 3849 | FIT |
| Spark-X2.6-4B | IQ3_M | bartowski | FP16 | 6519 | 1673 | FIT |
| Spark-X2.6-4B | IQ3_M | bartowski | q4_0 | 3957 | 4235 | FIT |
| Spark-X2.6-4B | IQ3_M | bartowski | q8_0 | 4979 | 3213 | FIT |
| Spark-X2.6-4B | IQ3_XS | bartowski | FP16 | 6213 | 1979 | FIT |
| Spark-X2.6-4B | IQ3_XS | bartowski | q4_0 | 3651 | 4541 | FIT |
| Spark-X2.6-4B | IQ3_XS | bartowski | q8_0 | 4673 | 3519 | FIT |
| Spark-X2.6-4B | IQ3_XXS | bartowski | FP16 | 6107 | 2085 | FIT |
| Spark-X2.6-4B | IQ3_XXS | bartowski | q4_0 | 3545 | 4647 | FIT |
| Spark-X2.6-4B | IQ3_XXS | bartowski | q8_0 | 4567 | 3625 | FIT |
| Spark-X2.6-4B | IQ4_NL | bartowski | FP16 | 6889 | 1303 | FIT |
| Spark-X2.6-4B | IQ4_NL | bartowski | q4_0 | 4327 | 3865 | FIT |
| Spark-X2.6-4B | IQ4_NL | bartowski | q8_0 | 5349 | 2843 | FIT |
| Spark-X2.6-4B | IQ4_XS | bartowski | FP16 | 6619 | 1573 | FIT |
| Spark-X2.6-4B | IQ4_XS | bartowski | q4_0 | 4057 | 4135 | FIT |
| Spark-X2.6-4B | IQ4_XS | bartowski | q8_0 | 5079 | 3113 | FIT |
| Spark-X2.6-4B | Q2_K | bartowski | FP16 | 5925 | 2267 | FIT |
| Spark-X2.6-4B | Q2_K | bartowski | q4_0 | 3363 | 4829 | FIT |
| Spark-X2.6-4B | Q2_K | bartowski | q8_0 | 4385 | 3807 | FIT |
| Spark-X2.6-4B | Q3_K_L | XHToken | FP16 | 6669 | 1523 | FIT |
| Spark-X2.6-4B | Q3_K_L | XHToken | q4_0 | 4107 | 4085 | FIT |
| Spark-X2.6-4B | Q3_K_L | XHToken | q8_0 | 5129 | 3063 | FIT |
| Spark-X2.6-4B | Q3_K_M | XHToken | FP16 | 6453 | 1739 | FIT |
| Spark-X2.6-4B | Q3_K_M | XHToken | q4_0 | 3891 | 4301 | FIT |
| Spark-X2.6-4B | Q3_K_M | XHToken | q8_0 | 4913 | 3279 | FIT |
| Spark-X2.6-4B | Q3_K_S | bartowski | FP16 | 6205 | 1987 | FIT |
| Spark-X2.6-4B | Q3_K_S | bartowski | q4_0 | 3643 | 4549 | FIT |
| Spark-X2.6-4B | Q3_K_S | bartowski | q8_0 | 4665 | 3527 | FIT |
| Spark-X2.6-4B | Q4_0 | bartowski | FP16 | 6689 | 1503 | FIT |
| Spark-X2.6-4B | Q4_0 | bartowski | q4_0 | 4127 | 4065 | FIT |
| Spark-X2.6-4B | Q4_0 | bartowski | q8_0 | 5149 | 3043 | FIT |
| Spark-X2.6-4B | Q4_1 | bartowski | FP16 | 6909 | 1283 | FIT |
| Spark-X2.6-4B | Q4_1 | bartowski | q4_0 | 4347 | 3845 | FIT |
| Spark-X2.6-4B | Q4_1 | bartowski | q8_0 | 5369 | 2823 | FIT |
| Spark-X2.6-4B | Q4_K_L | bartowski | FP16 | 7071 | 1121 | FIT |
| Spark-X2.6-4B | Q4_K_L | bartowski | q4_0 | 4509 | 3683 | FIT |
| Spark-X2.6-4B | Q4_K_L | bartowski | q8_0 | 5531 | 2661 | FIT |
| Spark-X2.6-4B | Q4_K_M | official | FP16 | 7115 | 1077 | FIT |
| Spark-X2.6-4B | Q4_K_M | official | q4_0 | 4557 | 3635 | FIT |
| Spark-X2.6-4B | Q4_K_M | official | q8_0 | 5579 | 2613 | FIT |
| Spark-X2.6-4B | Q4_K_S | XHToken | FP16 | 6703 | 1489 | FIT |
| Spark-X2.6-4B | Q4_K_S | XHToken | q4_0 | 4141 | 4051 | FIT |
| Spark-X2.6-4B | Q4_K_S | XHToken | q8_0 | 5163 | 3029 | FIT |
| Spark-X2.6-4B | Q5_K_M | XHToken | FP16 | 7229 | 963 | FLAGGED (spare <1024) |
| Spark-X2.6-4B | Q5_K_M | XHToken | q4_0 | 4667 | 3525 | FIT |
| Spark-X2.6-4B | Q5_K_M | XHToken | q8_0 | 5689 | 2503 | FIT |
| Spark-X2.6-4B | Q5_K_S | XHToken | FP16 | 7133 | 1059 | FIT |
| Spark-X2.6-4B | Q5_K_S | XHToken | q4_0 | 4571 | 3621 | FIT |
| Spark-X2.6-4B | Q5_K_S | XHToken | q8_0 | 5593 | 2599 | FIT |
| Spark-X2.6-4B | Q6_K | XHToken | FP16 | 7611 | 581 | FLAGGED (spare <1024) |
| Spark-X2.6-4B | Q6_K | XHToken | q4_0 | 5049 | 3143 | FIT |
| Spark-X2.6-4B | Q6_K | XHToken | q8_0 | 6071 | 2121 | FIT |
| Spark-X2.6-4B | Q6_K_L | bartowski | FP16 | 7993 | 199 | FLAGGED (spare <1024) |
| Spark-X2.6-4B | Q6_K_L | bartowski | q4_0 | 5431 | 2761 | FIT |
| Spark-X2.6-4B | Q6_K_L | bartowski | q8_0 | 6453 | 1739 | FIT |
| Spark-X2.6-4B | Q6_K_S | bartowski | FP16 | 7683 | 509 | FLAGGED (spare <1024) |
| Spark-X2.6-4B | Q6_K_S | bartowski | q4_0 | 5121 | 3071 | FIT |
| Spark-X2.6-4B | Q6_K_S | bartowski | q8_0 | 6143 | 2049 | FIT |
| Spark-X2.6-4B | Q8_0 | official | FP16 | - | - | FAIL @102400 |
| Spark-X2.6-4B | Q8_0 | official | q4_0 | 5989 | 2203 | FIT |
| Spark-X2.6-4B | Q8_0 | official | q8_0 | 7011 | 1181 | FIT |
