# VX: HTTP API

VX runs an embedded HTTP API on `127.0.0.1:9876` (the port is set
in Settings > MCP / API, or with `--port N` on the command line).
Every tool of the MCP server in [`../mcp/`](../mcp/) calls it, and
any language that can speak HTTP can drive VX the same way.

**Licence:** MIT, see [`LICENSE`](LICENSE).

**Status:** API version 2 (`GET /ping` answers `"api_version":2`),
as VX 0.10.0 serves it. Schema lives in
[`openapi.yaml`](openapi.yaml); worked examples live in
[`examples/`](examples/).

---

## Endpoints (high level)

| Endpoint               | Method | Purpose                                                                                  |
|------------------------|--------|------------------------------------------------------------------------------------------|
| `/ping`                | GET    | Liveness check. Returns `{status, app, api_version}`.                                    |
| `/state`               | GET    | Full snapshot: view, groups, tracks, chromosomes, config, the last session restore.      |
| `/screenshot`          | GET    | PNG of the entire VX window. Supports `?scale=` from 0.25 to 8.                          |
| `/screenshot/full`     | GET    | Alias for `/screenshot`.                                                                 |
| `/screenshot/viewport` | GET    | PNG of the track area alone, rendered off screen. Supports `?scale=` from 0.25 to 8.     |
| `/screenshot/track`    | GET    | PNG of a single visible track (with label area). Requires `?name=<track_name>`; `&scale=`. |
| `/navigate`            | POST   | Direct navigation, body `{chromosome, start, end}`; the MCP tool `vx_navigate` uses it.  |
| `/command`             | POST   | Entry point for every other action. Body: `{"command": "...", "params": {...}}`.         |

Every capture is rendered, never read from the screen, and the PNG
is RGB without an alpha channel. A scale outside 0.25 to 8 is
refused (400); a capture that cannot be rendered, as on a viewer
without a display, answers 503 `NO_RENDER` with the reason.

The vast majority of functionality goes through `POST /command`.
Most MCP tools send the command named like the tool without its
`vx_` prefix, with the same parameters. For example, the MCP tool
`vx_zoom(factor)` sends:

```json
{ "command": "zoom", "params": { "factor": 2.0 } }
```

The exceptions: `vx_ping`, `vx_get_state`, `vx_screenshot` and
`vx_screenshot_track` use the `GET` endpoints; `vx_navigate`
posts to `/navigate`; `vx_run_analysis(analysis=...)` sends
`run_analysis` with the name as `type`; `vx_set_config` sends its
keys as `showGrid`, `showLabels`, `darkMode`, `trackHeight`,
`activeModeEnabled`, `interfaceScale`, `fontScale` and
`apply_to_existing`; `vx_add_aggregate_track` and
`vx_set_aggregate_options` send their `options` as parameters of
the command; and `vx_load_demo` without a case sends
`demo_status`.

---

## Command catalogue (55 total)

| Category           | Commands                                                                                                    |
|--------------------|-------------------------------------------------------------------------------------------------------------|
| File loading       | `load_file`                                                                                                 |
| Track management   | `set_track_visibility`, `set_track_height`, `set_track_scroll`, `remove_track`, `reorder_track`             |
| Group management   | `create_group`, `switch_group`, `remove_group`                                                              |
| Navigation         | `navigate`, `zoom`, `pan`, `next_coverage_region`, `cancel_coverage_scan`                                   |
| Data queries       | `get_sequence`, `get_genes`, `search_genes`                                                                 |
| Config             | `set_config`, `set_magnifier`                                                                               |
| Selection          | `select_region`, `click_element`                                                                            |
| Export             | `export_region`, `export_svg`, `export_image`, `svg_export_status`                                          |
| Loading state      | `loading_status`, `cancel_loading`                                                                          |
| Bookmarks          | `add_bookmark`, `list_bookmarks`, `remove_bookmark`, `goto_bookmark`                                        |
| Chromosomes        | `list_chromosomes`                                                                                          |
| Track options      | `set_signal_options`, `set_variant_options`, `set_interaction_options`, `set_alignment_options`             |
| Read aggregates and transcript DTI | `add_aggregate_track`, `set_aggregate_options`, `aggregate_rows`, `add_dti_track`, `set_dti_options`, `dti_lookup` |
| Analysis           | `list_analyses`, `run_analysis`, `analysis_status`, `cancel_analysis`, `read_result_rows`                   |
| Video recording    | `start_recording`, `stop_recording`, `recording_status`                                                     |
| Sessions and the process | `save_session`, `load_session`, `shutdown`                                                            |
| Demo data          | `load_demo`, `demo_status`                                                                                  |

Two commands answer when their work ends, not at once:
`next_coverage_region` (when its scan ends, which on a whole
chromosome of a large BAM can take a minute or more) and
`read_result_rows` (when its page is read). Give them no short
client timeout.

See [`openapi.yaml`](openapi.yaml) for full parameter and response
schemas, and the per-command request bodies under
`#/components/schemas/RequestCommand_*`.

---

## Quick liveness check

```bash
curl -s http://127.0.0.1:9876/ping
# {"status":"ok","app":"VX","api_version":2}
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

The chromosome is given back as the loaded reference names it
(`1` and `chr1` find the same sequence).

---

## Error model

Failed commands return a JSON body with:

* `error`:    human-readable message
* `code`:     machine-readable code (below)
* `details`:  optional remediation hint

Since 0.10.0 the HTTP status follows the code (a success is 200):

| Status | Codes | When |
|---|---|---|
| 400 | `INVALID_PARAMS`, `PARSE_ERROR`, `UNKNOWN_ANALYSIS`, `NOT_SUPPORTED` | A request the client can mend: a parameter missing or out of range, a body that is not JSON, an analysis the catalogue lacks, a track of the wrong kind |
| 403 | `NOT_A_RESULT` | A path `read_result_rows` does not read |
| 404 | `UNKNOWN_COMMAND`, `UNKNOWN_ENDPOINT`, `NOT_FOUND` (and any code ending in `_NOT_FOUND`) | A name that is not there: command, path, track, group, chromosome, bookmark, file |
| 405 | `METHOD_NOT_ALLOWED` | `OPTIONS`: the API takes `GET` and `POST` |
| 409 | `BUSY`, `INVALID_STATE`, `NO_REFERENCE`, `NO_ANNOTATION` | A state the request conflicts with: a coverage scan or a demo download already running, a recording, analysis or SVG export already in progress, nothing loaded to export |
| 501 | `NOT_IMPLEMENTED` | Not implemented in this version |
| 503 | `NOT_READY`, `NO_RENDER` | The viewer cannot serve it now: still starting, no reference loaded, Active Mode off for `click_element`, no OpenGL context for a capture |
| 504 | `TIMEOUT`, `STALLED` | The window did not answer in time (the request may still be carried out; ask for `/state`), or a coverage scan read nothing for 60 s |
| 500 | `OPERATION_FAILED`, `IO_ERROR`, `DEPENDENCY_MISSING`, `INTERNAL_ERROR`, and an error without a code | The operation was attempted and failed (a file that cannot be read or written, ffmpeg missing, an internal error) |

Each request gets its own answer. The window's answer is awaited
for the API timeout (Settings > Appearance > Performance, 30 s by
default); a later answer is dropped and named in the log.

---

## Worked examples

* [`examples/curl_navigate.sh`](examples/curl_navigate.sh): end-to-end
  bash walk-through: ping, load a file, navigate, screenshot.
* [`examples/python_client.py`](examples/python_client.py): minimal
  zero-dependency Python client using only the stdlib.
* [`examples/claude_mcp_recipes.md`](examples/claude_mcp_recipes.md):
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
other machines on the network. There is no authentication: the
security model is "if you can talk to localhost on this machine,
you already have user-level access to VX's data". The API sends
no CORS headers and answers `OPTIONS` with 405, so a page in a
web browser cannot drive it.

If you want remote access, run an SSH tunnel:

```bash
ssh -L 9876:127.0.0.1:9876 user@remote-host
# then on the local machine:
curl -s http://127.0.0.1:9876/ping
```

Do **not** expose port 9876 to a public interface.
