#!/usr/bin/env bash
# Hygiene gate: fails (exit 1) if any personal-identifying or environment-leaking
# pattern appears in tracked files. Run in CI on every push and locally before
# committing. Checks git HISTORY too when invoked with --history.
#
# Usage: scripts/hygiene-check.sh [--history]
set -uo pipefail

PATTERNS='redacted|redacted|redacted|redacted|10\.0\.0\.|100\.[0-9]+\.|@gmail\.|@icloud\.|/Users/|/home/[a-z]|redacted|redacted|dgx'

FAIL=0

scan_tree() {
    # Scan working tree files that git tracks (respects .gitignore implicitly)
    while IFS= read -r -d '' f; do
        if grep -Iq . "$f" 2>/dev/null; then
            MATCHES=$(grep -inE "$PATTERNS" "$f" 2>/dev/null || true)
            if [ -n "$MATCHES" ]; then
                echo "HIT: $f"
                echo "$MATCHES" | head -5
                FAIL=1
            fi
        fi
    done < <(git ls-files -z --cached --others --exclude-standard)
}

scan_history() {
    # Scan every blob in history for patterns (expensive but thorough; run pre-publish)
    echo "Scanning full git history..."
    HITS=$(git log --all -p | grep -inE "$PATTERNS" | head -20 || true)
    if [ -n "$HITS" ]; then
        echo "HISTORY HITS:"
        echo "$HITS"
        FAIL=1
    fi
}

echo "== hygiene gate: scanning tracked files =="
scan_tree

if [ "${1:-}" = "--history" ]; then
    scan_history
fi

if [ "$FAIL" -eq 1 ]; then
    echo "== FAILED: personal/secret patterns found. Remove them before pushing. =="
    exit 1
fi
echo "== hygiene gate: clean =="
