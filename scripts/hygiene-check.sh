#!/usr/bin/env bash
# Hygiene gate: fails (exit 1) if any personal-identifying or environment-leaking
# pattern appears in tracked files. Run in CI on every push and locally before
# committing. Checks git HISTORY too when invoked with --history.
#
# STRICT standard (2026-11-08): NO real names — including the operator's first
# name — in tracked content, and no environment hostnames (workstations,
# servers, network nodes). Content is gated in every mode. Commit METADATA is
# report-only in the default mode (the repo history predates this standard and is
# not rewritten in place) and FATAL under --history: that mode is the pre-publish
# check, and a publish candidate must not carry a private identity — a name, a
# personal email, a private hostname or the internal audit-lane handle — in any
# author or committer field, where every stranger's `git log` can read it.
# Fixing identities is what a mailmap (or a filtered clone) is for; the gate
# cannot fix them, so it must not report them as clean.
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
# Whitelisted (public, operator-approved 2026-09-26): the GitHub org name in repo URLs.
# Strip it before scanning so repo links don't trip the handle pattern.
sanitize() {
    # Comments must stay OUTSIDE the pipeline: a backslash continuation followed
    # by a comment line breaks the command.
    #
    # 1. public repo URL org references, so repo links don't trip the handle rule
    # 2. "redacted"/"redaction" — ordinary English and the OCR suite's field
    #    name, not a leak marker (the `redacted` fragment was over-broad).
    #    NOTE: the first name is NOT stripped any more — under the strict
    #    standard it is screened in content like every other real name.
    sed -E -e 's#github\.com/TysAIs/#GITHUB-ORG/#g' \
           -e 's#TysAIs/slm-gauntlet#ORG/slm-gauntlet#g' \
           -e 's/redact(ed|ion)//Ig'
}
E1='@g'; E2='mail.'
F1='/U'; F2='sers/'
G1='all'; G2='spark'
# Environment hostnames, screened as PREFIX fragments so variants (name-1,
# name_2, name.local) are caught too: the workstation host, the PVE box, the
# NAS and the two network nodes. Fragments again — never the literal values.
H1='ar'; H2='eo'
I1='pr'; I2='ometheus'
J1='sa'; J2='nctum'
K1='ve'; K2='riton'
L1='ar'; L2='biter'
# The sweep lane's provider name and the internal audit-lane handle are the same
# class of leak as the hostnames above: they name private infrastructure. Built
# from fragments so GRUNT_HOST / grunt_health.sh (public env/script names that
# the docs legitimately quote) stay legal.
M1='gr'; M2='unt-pve'
N1='invi'; N2='ncible'
# Private address space the earlier revision missed. It screened only the first /24
# of the 10/8 block and bare 100/8 prefixes; RFC1918 class B/C and the carrier-grade
# NAT range a tailnet hands out were not screened, so a leaked tailnet address passed.
O1='192'; O2='\.168\.'
P1='172'; P2='\.(1[6-9]|2[0-9]|3[01])\.'
Q1='100'; Q2='\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.[0-9]'
# Literal lane identities: ssh alias values the sweep tooling used to default to,
# and the private dotfiles path that used to carry the staging key.
R1='p'; R2='ve-node'
S1='p'; S2='ve-lab'
T1='migration'; T2='-backup'
U1='--ssh '; U2='pve'
V1='ssh '; V2='pve'
PATTERNS="${A1}${A2}|${B1}${B2}|${C1}${C2}|${D1}${D2}|10\\.0\\.0\\.|100\\.[0-9]+\\.|${E1}${E2}|@icloud\\.|${F1}${F2}|/home/[a-z]|${G1}${G2}|redacted|dgx|${H1}${H2}|${I1}${I2}|${J1}${J2}|${K1}${K2}|${L1}${L2}|${M1}${M2}|${N1}${N2}|${O1}${O2}|${P1}${P2}|${Q1}${Q2}|${R1}${R2}|${S1}${S2}|${T1}${T2}|${U1}${U2}|${V1}${V2}"

FAIL=0
STRICT_IDENT=0

# Identity screening set: the personal names, the personal email domains, the
# internal handle, the provider name and the private hostnames. Deliberately
# narrower than PATTERNS: the sanctioned org identity (handle + org repo URLs)
# is legal in metadata, and 'redacted'/'dgx'/local paths are content concerns.
IDENT_PAT="${A1}${A2}|${B1}${B2}|${C1}${C2}|${E1}${E2}|@icloud\\.|${G1}${G2}|${H1}${H2}|${I1}${I2}|${J1}${J2}|${K1}${K2}|${L1}${L2}|${M1}${M2}|${N1}${N2}"

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
    #
    # --format is required, not cosmetic: without it `git log -p` prints its own
    # commit headers, and every commit the sanctioned org identity authored then
    # matches the org-name pattern — a gate that cannot pass on clean history.
    # Identity is scan_metadata's job (report-only); this scan is about content.
    echo "Scanning full git history..."
    HITS=$(git log --all -p --format='commit %h' -- . ':!scripts/hygiene-check.sh' \
           | sanitize | grep -inE "$PATTERNS" || true)
    if [ -n "$HITS" ]; then
        echo "HISTORY HITS ($(printf '%s\n' "$HITS" | grep -c . )):"
        printf '%s\n' "$HITS" | head -20
        FAIL=1
    fi
}

scan_metadata() {
    # Author/committer identities. Report-only in the default mode: the history
    # predates the strict standard and is not rewritten in place, so the hits are
    # listed for the record. Under --history they FAIL, because that mode exists
    # to clear a publish candidate and an identity leak is readable by anyone.
    #
    # Screening only the personal-email fragment was the blind spot: 12 commits
    # authored under the internal audit-lane handle passed as "no personal
    # identity". IDENT_PAT covers names, personal email, private hostnames, the
    # provider name and the handle; the sanctioned org identity is not in it.
    echo "== commit metadata =="
    ALL_IDENTS=$(git log --all --format='%H %an <%ae> | %cn <%ce>' | sort -u || true)
    MHITS=$(printf '%s\n' "$ALL_IDENTS" | grep -iE "${E1}${E2}|@icloud\\." || true)
    if [ -n "$MHITS" ]; then
        echo "METADATA NOTE: commits carrying a personal email (pre-standard, kept as-is):"
        echo "$MHITS" | head -20
        echo "METADATA NOTE: fix is forward-only for new commits, or a mailmap for the history."
    fi
    IHITS=$(printf '%s\n' "$ALL_IDENTS" | grep -iE "$IDENT_PAT" || true)
    if [ -n "$IHITS" ]; then
        if [ "$STRICT_IDENT" -eq 1 ]; then
            echo "METADATA HITS ($(printf '%s\n' "$IHITS" | grep -c . )): private identity in an author/committer field:"
            printf '%s\n' "$IHITS" | head -20
            echo "METADATA: FAIL — a publish candidate must not carry these; apply the mailmap leg."
            FAIL=1
        else
            echo "METADATA NOTE: $(printf '%s\n' "$IHITS" | grep -c . ) commits carry a private identity (pre-standard, kept as-is); --history lists them and fails."
        fi
    else
        echo "METADATA: no personal identity found in commit metadata."
    fi
}

echo "== hygiene gate: scanning tracked files =="
scan_tree

STRICT_IDENT=0
if [ "${1:-}" = "--history" ]; then
    STRICT_IDENT=1
fi
scan_metadata

if [ "${1:-}" = "--history" ]; then
    scan_history
fi

if [ "$FAIL" -eq 1 ]; then
    echo "== FAILED: personal/secret patterns found. Remove them before pushing. =="
    exit 1
fi
echo "== hygiene gate: clean =="
