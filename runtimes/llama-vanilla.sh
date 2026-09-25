# Runtime recipe: llama.cpp (vanilla) serving wrapper.
# Usage: runtimes/llama-vanilla.sh <model.gguf> [port] [context] [parallel-slots]
# Recipes for specific model+quant combos live in runtimes/recipes/*.yaml
# and override these defaults via the runner.
set -euo pipefail

MODEL="${1:?usage: llama-vanilla.sh <model.gguf> [port] [ctx] [np]}"
PORT="${2:-8080}"
CTX="${3:-32768}"
NP="${4:-8}"

exec llama-server \
    -m "$MODEL" \
    --host 0.0.0.0 \
    --port "$PORT" \
    -c "$CTX" \
    -np "$NP" \
    --kv-unified \
    -fa \
    --jinja \
    --temp 0.0
