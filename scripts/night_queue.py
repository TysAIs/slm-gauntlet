#!/usr/bin/env python3
"""Night queue driver: run every model through the newest gauntlet end-to-end.

Runs LOCALLY (Mac). For each model: swap CT server via ssh, wait for endpoint,
Bonsai uses the PrismML fork binary.
"""
import os as _os
import subprocess
import sys
import time

_SSH_ALIAS = _os.environ.get("GAUNTLET_SSH_ALIAS", "pve-lab")
CT = ["ssh", "-o", "ConnectTimeout=15", _SSH_ALIAS, "pct", "exec", "100", "--"]
PORT = "18081"

CT_HOST = _os.environ.get("GAUNTLET_CT_HOST", "localhost")
ENDPOINT = f"http://{CT_HOST}:{PORT}/v1"

MODELS = [
    # (name, path, ctx, np, binary)  binary: LLAMA | PRISM
    ("qwen3.5-4b-q4_K_M", "qwen3.5-4b/Qwen3.5-4B-Q4_K_M.gguf", "32768", "2", "LLAMA"),
    ("sharp-spark-4b-q4_K_XL", "sharp-spark-4b/Sharp-Spark-X2.5-4B-Q4_K_XL.gguf", "32768", "2", "LLAMA"),
    ("lfm2.5-2.6b-q4_K_M", "lfm2.5-2.6b/LFM2.5-2.6B-Q4_K_M.gguf", "32768", "2", "LLAMA"),
    ("lfm2.5-2.6b-q8_0", "lfm2.5-2.6b/LFM2.5-2.6B-Q8_0.gguf", "32768", "2", "LLAMA"),
    ("gemma-e4b-q4_K_M", "gemma-e4b/gemma-3n-E4B-it-Q4_K_M.gguf", "16384", "1", "LLAMA"),
    ("mimo-9b-q4_K_M", "mimo-9b/MiMo-V2.6-Distill-Qwen-9B-Q4_K_M.gguf", "8192", "1", "LLAMA"),
    ("ornith-9b-q4_K_M", "ornith-9b/Ornith-1.5-9B-Q4_K_M.gguf", "8192", "1", "LLAMA"),
    ("gemma4-e4b-q4_K_M", "gemma4-e4b/google_gemma-4-E4B-it-Q4_K_M.gguf", "32768", "2", "LLAMA"),
    ("gemma4-12b-ud-q2_K_XL", "gemma4-12b/gemma-4-12b-it-UD-Q2_K_XL.gguf", "16384", "1", "LLAMA"),
    ("gemma4-12b-iq3_XXS", "gemma4-12b/gemma-4-12B-it-IQ3_XXS.gguf", "16384", "1", "LLAMA"),
    ("bonsai2-ptq1_0", "bonsai-2/Ternary-Bonsai-2-27B-PTQ1_0.gguf", "8192", "1", "PRISM"),
]


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def swap_server(name, rel_path, ctx, np_, binary):
    path = f"/mnt/data/models/{rel_path}"
    server = ("/opt/prism-llama.cpp/build-cuda/bin/llama-server" if binary == "PRISM"
              else "/opt/llama.cpp/build/bin/llama-server")
    # kill old server FIRST, as its own ssh exec (script file must not contain the
    # kill pattern or it kills itself; separate exec avoids that)
    sh(CT + ["bash", "-c", f"pkill -f 'llama-server.*port {PORT}' 2>/dev/null; true"])
    time.sleep(3)
    script = (f"setsid nohup {server} -m {path} --alias {name} --host 0.0.0.0 "
              f"--port {PORT} --jinja -ngl 99 -t 6 -tb 6 -c {ctx} -np {np_} "
              f"--kv-unified -ctk q8_0 -ctv q8_0 -fa on --reasoning-budget 0 "
              f"--no-reasoning-preserve --temp 0.0 </dev/null > /tmp/srv_{name}.log 2>&1 &\n")
    # write script via stdin then execute detached (proven pattern)
    sh(CT + ["tee", "/tmp/nq_start.sh"], input=script)
    subprocess.run(CT + ["bash", "-c",
                    "setsid bash /tmp/nq_start.sh </dev/null >/dev/null 2>&1 &"],
                   capture_output=True, timeout=30)
    time.sleep(2)
    for _ in range(120):
        time.sleep(2)
        r = subprocess.run(["curl", "-s", "--max-time", "3", f"{ENDPOINT}/models"],
                           capture_output=True)
        if name.encode() in r.stdout:  # RIGHT model must answer, not a stale one
            return True
    return False


def main():
    log = open("/tmp/night_queue.log", "a", buffering=1)
    # free the GPU: stop production service during the queue
    sh(CT + ["systemctl", "stop", "llama-mini@18080"])
    log.write("=== llama-mini stopped for queue ===\n")
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    for name, path, ctx, np_, binary in MODELS:
        if only and name not in only:
            continue
        log.write(f"=== {name} start {time.strftime('%H:%M:%S')} ===\n")
        if not swap_server(name, path, ctx, np_, binary):
            log.write(f"=== {name} SERVER FAILED ===\n")
            continue
        # full gauntlet
        r = sh(["bash", "-c",
                f".venv/bin/python -m gauntlet.cli run --endpoint {ENDPOINT} "
                f"--model {name} --suite all --concurrency 2 --timeout 240 --seed 1 "
                f"> /tmp/gauntlet_{name}.log 2>&1; echo RC=$?"], timeout=580)
        log.write(f"=== {name} gauntlet rc={r.stdout.strip()[-6:]} {time.strftime('%H:%M:%S')} ===\n")
        log.write(f"=== {name} COMPLETE {time.strftime('%H:%M:%S')} ===\n")
    # restore production
    sh(CT + ["pkill", "-f", f"port {PORT}"])
    sh(CT + ["systemctl", "start", "llama-mini@18080"])
    log.write("=== QUEUE COMPLETE ===\n")


if __name__ == "__main__":
    main()
