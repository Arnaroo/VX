# VX Genome Viewer — HTTP API

VX runs an embedded HTTP API on `127.0.0.1:9876`. Every MCP tool
in the [`../mcp/`](../mcp/) catalogue is also reachable as a plain
HTTP endpoint, so any language that can speak HTTP can drive VX.

**License:** MIT — see [`LICENSE`](LICENSE).

**Status:** Stable as of v0.9.0. Schema lives in
[`openapi.yaml`](openapi.yaml); worked examples live in
[`examples/`](examples/).

---

## Endpoints (high level)

| Endpoint               | Method | Purpose                                                                                  |
|------------------------|--------|------------------------------------------------------------------------------------------|
| `/ping`                | GET    | Liveness check. Returns `{status, app, api_version}`.                                    |
| `/state`               | GET    | Full snapshot — viewport, groups, tracks, chromosomes, config.                           |
| `/screenshot`          | GET    | PNG of the entire VX window.                                                             |
| `/screenshot/full`     | GET    | Alias for `/screenshot`.                                                                 |
| `/screenshot/viewport` | GET    | PNG of just the GL viewport. Supports `?scale=` for high-DPI capture.                    |
| `/screenshot/track`    | GET    | PNG of a single track (with label area). Requires `?name=<track_name>`.                  |
| `/navigate`            | POST   | Legacy direct navigation, preserved for back-compat with v1 clients.                     |
| `/command`             | POST   | Single entry point for every action. Body: `{"command": "...", "params": {...}}`.        |

The vast majority of functionality goes through `POST /command`.
The command name and parameter shape match the corresponding MCP
tool 1:1, with one rule: the MCP tool name is the underlying HTTP
command **without** the `vx_` prefix. For example, the MCP tool
`vx_navigate(chromosome, start, end)` sends:

```json
{ "command": "navigate", "params": { "chromosome": "chr1", "start": 1000000, "end": 1500000 } }
```

---

## Command catalogue (40 total)

| Category           | Commands                                                                                                    |
|--------------------|-------------------------------------------------------------------------------------------------------------|
| File loading       | `load_file`                                                                                                 |
| Track management   | `set_track_visibility`, `set_track_height`, `set_track_scroll`, `remove_track`, `reorder_track`             |
| Group management   | `create_group`, `switch_group`, `remove_group`                                                              |
| Navigation         | `navigate`, `zoom`, `pan`, `next_coverage_region`                                                           |
| Data queries       | `get_sequence`, `get_genes`, `search_genes`                                                                 |
| Config             | `set_config`, `set_magnifier`                                                                               |
| Selection          | `select_region`                                                                                             |
| Export             | `export_region`, `export_svg`, `svg_export_status`                                                          |
| Loading state      | `loading_status`, `cancel_loading`                                                                          |
| Bookmarks          | `add_bookmark`, `list_bookmarks`, `remove_bookmark`, `goto_bookmark`                                        |
| Chromosomes        | `list_chromosomes`                                                                                          |
| Track options      | `set_signal_options`, `set_variant_options`, `set_interaction_options`, `set_alignment_options`             |
| Analysis           | `list_analyses`, `run_analysis`, `analysis_status`, `cancel_analysis`                                       |
| Video recording    | `start_recording`, `stop_recording`, `recording_status`                                                     |

See [`openapi.yaml`](openapi.yaml) for full parameter and response
schemas, and the per-command request bodies under
`#/components/schemas/RequestCommand_*`.

---

## Quick liveness check

```bash
curl -s http://127.0.0.1:9876/ping
# {"status":"ok","app":"VX Genome Viewer","api_version":2}
```

---

## Quick command example

```bash
curl -s http://127.0.0.1:9876/command \
  -H 'Content-Type: application/json' \
  -d '{"command":"navigate","params":{"chromosome":"chr1","start":1000000,"end":1500000}}'
```

Response:

```json
{ "success": true, "chromosome": "chr1", "start": 1000000, "end": 1500000 }
```

---

## Error model

Failed commands return a JSON body with at least:

* `error`   — human-readable message
* `code`    — one of:
  - `INVALID_PARAMS` — required field missing or out of range
  - `NOT_FOUND` — track/group/chromosome/bookmark/file does not exist
  - `NOT_READY` — VX is still loading data or has no active group
  - `INVALID_STATE` — action conflicts with current state (e.g. recording already in progress)
  - `OPERATION_FAILED` — operation attempted but failed (renderer, parser, etc.)
  - `UNKNOWN_COMMAND` — `command` field did not match any known dispatch
  - `UNKNOWN_ENDPOINT` — HTTP path is not served by VX
  - `DEPENDENCY_MISSING` — external tool not installed (e.g. ffmpeg)
  - `TIMEOUT` — GTK dispatch deadlocked or exceeded server timeout
  - `PARSE_ERROR` — request body was not valid JSON
  - `INTERNAL_ERROR` — server-side exception
  - `NOT_SUPPORTED` — operation valid for some track types but not this one
* `details` — optional remediation hint

---

## Worked examples

* [`examples/curl_navigate.sh`](examples/curl_navigate.sh) — end-to-end
  bash walk-through: ping, load a file, navigate, screenshot.
* [`examples/python_client.py`](examples/python_client.py) — minimal
  zero-dependency Python client using only the stdlib.
* [`examples/claude_mcp_recipes.md`](examples/claude_mcp_recipes.md) —
  MCP-side recipes for common agent workflows.

---

## Validation

The spec is OpenAPI 3.1. To validate locally:

```bash
# Option 1: swagger-cli (npm)
npx @apidevtools/swagger-cli validate openapi.yaml

# Option 2: redocly
npx @redocly/cli lint openapi.yaml

# Option 3: openapi-spec-validator (Python)
pip install openapi-spec-validator
openapi-spec-validator openapi.yaml
```

---

## Security and bind address

The server binds to `127.0.0.1` only. It is **not** reachable from
other machines on the network. There is no authentication — the
security model is "if you can talk to localhost on this machine,
you already have user-level access to VX's data".

If you want remote access, run an SSH tunnel:

```bash
ssh -L 9876:127.0.0.1:9876 user@remote-host
# then on the local machine:
curl -s http://127.0.0.1:9876/ping
```

Do **not** expose port 9876 to a public interface.

