#!/usr/bin/env bash
# curl_navigate.sh — end-to-end bash walk-through of the VX HTTP API.
#
# Demonstrates: ping, state introspection, file loading, navigation,
# region screenshot, sequence retrieval, gene lookup. Run with VX
# already open (start it manually, then run this script).
#
# Usage:
#   ./curl_navigate.sh /absolute/path/to/reference.fa /absolute/path/to/annotations.gtf
# or with no args to drive a VX that already has files loaded.

set -euo pipefail

VX="${VX_BASE:-http://127.0.0.1:9876}"
FASTA="${1:-}"
GTF="${2:-}"

# ── helpers ────────────────────────────────────────────────────────────
hr() { printf -- '─%.0s' {1..72}; printf '\n'; }
say() { hr; printf ' %s\n' "$*"; hr; }

cmd() {
    local name="$1"; shift
    local body="$1"; shift
    say "POST /command  $name"
    curl -sS "$VX/command" \
        -H 'Content-Type: application/json' \
        -d "$body" \
        | sed 's/^/  /'
    printf '\n'
}

# ── 1. liveness check ──────────────────────────────────────────────────
say 'GET /ping'
curl -sS "$VX/ping" | sed 's/^/  /'
printf '\n'

# ── 2. discover current state ─────────────────────────────────────────
say 'GET /state'
curl -sS "$VX/state" | head -c 800 | sed 's/^/  /'
printf '\n  ...\n\n'

# ── 3. (optional) load a FASTA reference ──────────────────────────────
if [[ -n "$FASTA" ]]; then
    cmd load_file "$(printf '{"command":"load_file","params":{"path":"%s"}}' "$FASTA")"

    # Poll until the load completes
    for _ in $(seq 1 60); do
        status=$(curl -sS "$VX/command" -H 'Content-Type: application/json' \
            -d '{"command":"loading_status"}')
        echo "  $status"
        if echo "$status" | grep -q '"done":true'; then break; fi
        sleep 1
    done
fi

# ── 4. (optional) load a GTF annotation ───────────────────────────────
if [[ -n "$GTF" ]]; then
    cmd load_file "$(printf '{"command":"load_file","params":{"path":"%s"}}' "$GTF")"

    for _ in $(seq 1 60); do
        status=$(curl -sS "$VX/command" -H 'Content-Type: application/json' \
            -d '{"command":"loading_status"}')
        if echo "$status" | grep -q '"done":true'; then break; fi
        sleep 1
    done
fi

# ── 5. list chromosomes ───────────────────────────────────────────────
cmd list_chromosomes '{"command":"list_chromosomes"}'

# ── 6. navigate to BRCA1 (chr17, hg38) ─────────────────────────────────
cmd navigate '{"command":"navigate","params":{"chromosome":"chr17","start":43044295,"end":43125483}}'

# ── 7. get the DNA sequence under the cursor ──────────────────────────
cmd get_sequence '{"command":"get_sequence","params":{"chromosome":"chr17","start":43044295,"end":43044395}}'

# ── 8. search for a gene by name ──────────────────────────────────────
cmd search_genes '{"command":"search_genes","params":{"query":"BRCA1"}}'

# ── 9. capture the viewport as PNG ────────────────────────────────────
say 'GET /screenshot/viewport?scale=2.0  →  /tmp/vx_viewport.png'
curl -sS -o /tmp/vx_viewport.png "$VX/screenshot/viewport?scale=2.0"
file /tmp/vx_viewport.png | sed 's/^/  /'

# ── 10. zoom in 2× and capture again ──────────────────────────────────
cmd zoom '{"command":"zoom","params":{"factor":2.0}}'
curl -sS -o /tmp/vx_viewport_zoomed.png "$VX/screenshot/viewport?scale=2.0"
file /tmp/vx_viewport_zoomed.png | sed 's/^/  /'

say 'Done.'
