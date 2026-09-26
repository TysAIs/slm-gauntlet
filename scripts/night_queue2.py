#!/usr/bin/env python3
import os as _os
import subprocess
import sys
import time

_SSH_ALIAS = _os.environ.get("GAUNTLET_SSH_ALIAS", "pve-lab")
CT_HOST = _os.environ.get("GAUNTLET_CT_HOST", "localhost")
EP = f"http://{CT_HOST}:18081/v1"
CT = ["ssh", "-o", "ConnectTimeout=15", _SSH_ALIAS, "pct", "exec", "100", "--"]
MODELS = {
  "lfm2.5-2.6b-q8_0":      ("lfm2.5-2.6b/LFM2.5-2.6B-Q8_0.gguf", "32768", "2", "LLAMA"),
  "gemma-e4b-q4_K_M":      ("gemma-e4b/gemma-3n-E4B-it-Q4_K_M.gguf", "16384", "1", "LLAMA"),
  "mimo-9b-q4_K_M":        ("mimo-9b/MiMo-V2.6-Distill-Qwen-9B-Q4_K_M.gguf", "8192", "1", "LLAMA"),
  "ornith-9b-q4_K_M":      ("ornith-9b/Ornith-1.5-9B-Q4_K_M.gguf", "8192", "1", "LLAMA"),
  "gemma4-e4b-q4_K_M":     ("gemma4-e4b/google_gemma-4-E4B-it-Q4_K_M.gguf", "32768", "2", "LLAMA"),
}
SRVBIN = {"LLAMA": "/opt/llama.cpp/build/bin/llama-server",
          "PRISM": "/opt/prism-llama.cpp/build-cuda/bin/llama-server"}

def sh(c, timeout=60, **kw):
    return subprocess.run(c, capture_output=True, text=True, timeout=timeout, **kw)

def log(m):
    with open("/tmp/night_queue2.log", "a") as f:
        f.write(m + "\n")

def swap(name, rel, ctx, np_, bin_):
    sh(CT + ["pkill", "-f", "llama-server"])
    time.sleep(2)
    sh(CT + ["systemctl", "stop", "llama-mini@18080"])
    time.sleep(3)
    script = (f"setsid nohup {SRVBIN[bin_]} -m /mnt/data/models/{rel} --alias {name} "
              f"--host 0.0.0.0 --port 18081 --jinja -ngl 99 -t 6 -tb 6 -c {ctx} -np {np_} "
              f"--kv-unified -ctk q8_0 -ctv q8_0 -fa on --reasoning-budget 0 "
              f"--no-reasoning-preserve --temp 0.0 </dev/null > /tmp/srv_{name}.log 2>&1 &\n")
    sh(CT + ["tee", "/tmp/nq_start.sh"], input=script)
    r = sh(CT + ["nohup", "bash", "/tmp/nq_start.sh"], timeout=25)
    for _ in range(150):
        time.sleep(2)
        r = subprocess.run(["curl", "-s", "--max-time", "3", f"{EP}/models"], capture_output=True)
        if name.encode() in r.stdout:
            return True
    return False

def run(model):
    log(f"=== {model} start ===")
    rel, ctx, np_, bin_ = MODELS[model]
    if not swap(model, rel, ctx, np_, bin_):
        log(f"=== {model} SERVER FAILED ===")
        return False
    r = sh(["bash", "-c",
            f".venv/bin/python -m gauntlet.cli run --endpoint {EP} --model {model} "
            f"--suite all --concurrency 2 --timeout 240 --seed 1"], timeout=580)
    log(f"=== {model} gauntlet rc={r.returncode} ===")
    if r.returncode != 0:
        log(r.stdout[-200:] or r.stderr[-200:])
    return True

if __name__ == "__main__":
    for m in sys.argv[1:]:
        try:
            run(m)
        except Exception as e:
            log(f"=== {m} EXC {e} ===")
    log("=== QUEUE2 COMPLETE ===")
