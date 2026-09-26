#!/usr/bin/env bash
# Hygiene gate: fails (exit 1) if any personal-identifying or environment-leaking
# pattern appears in tracked files. Run in CI on every push and locally before
# committing. Checks git HISTORY too when invoked with --history.
#
# The pattern list below is assembled from fragments on purpose: this file must
# never contain the literal strings it screens for (it would flag itself).
#
# Usage: scripts/hygiene-check.sh [--history]
set -uo pipefail

# fragments (each is only part of the real token)
A1='it'; A2="x$(printf 'j')i"
B1='ty'; B2='ler'
C1='jer'; C2='man'
D1='ty'; D2="sa$(printf 'i')s"
# Whitelisted (public, Tyler-approved 2026-09-26): the GitHub org name in repo URLs.
# Strip it before scanning so repo links don't trip the handle pattern.
sanitize() {
    # remove public repo URL org references before pattern matching
    sed -E 's#github\.com/TysAIs/#GITHUB-ORG/#g; s#TysAIs/slm-gauntlet#ORG/slm-gauntlet#g'
}
E1='@g'; E2='mail.'
F1='/U'; F2='sers/'
G1='all'; G2="sp$(printf 'a')rk"
PATTERNS="${A1}${A2}|${B1}${B2}|${C1}${C2}|${D1}${D2}|10\\.0\\.0\\.|100\\.[0-9]+\\.|${E1}${E2}|@icloud\\.|${F1}${F2}|/home/[a-z]|${G1}${G2}|redacted|dgx"

FAIL=0

scan_tree() {
    # Scan working-tree files git tracks (respects .gitignore implicitly)
    # Skip this script: it contains regex fragments/escapes of the patterns
    # themselves (by design) and would always self-match.
    while IFS= read -r -d '' f; do
        [[ "$f" == *hygiene-check.sh ]] && continue
        if grep -Iq . "$f" 2>/dev/null; then
            MATCHES=$(grep -inE "$PATTERNS" <(sanitize < "$f") 2>/dev/null || true)
            if [ -n "$MATCHES" ]; then
                echo "HIT: $f"
                echo "$MATCHES" | head -5
                FAIL=1
            fi
        fi
    done < <(git ls-files -z --cached --others --exclude-standard)
}

scan_history() {
    # Scan every diff blob in history for patterns (run pre-publish)
    # Skip diffs of this script itself: it contains escaped regex fragments
    # of the patterns (by design) and would always self-match.
    echo "Scanning full git history..."
    HITS=$(git log --all -p -- . ':!scripts/hygiene-check.sh' | sanitize | grep -inE "$PATTERNS" | head -20 || true)
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
