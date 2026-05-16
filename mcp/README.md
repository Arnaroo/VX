# VX MCP Server

`vx_mcp_server.py` is an [MCP](https://modelcontextprotocol.io)
server that exposes VX Genome Viewer's HTTP API as a tool catalogue
for AI agents (Claude Code, Claude Desktop, and any other
MCP-compatible client).

**License:** MIT — see [`LICENSE`](LICENSE).

---

## What it does

VX runs an embedded HTTP API on `127.0.0.1:9876`. The MCP server
in this folder is a thin, dependency-light Python wrapper that:

- exposes 39+ MCP tools (one per VX command) to the agent;
- translates MCP tool invocations into HTTP POSTs against the
  running VX instance;
- streams back JSON responses, screenshots (as base64 PNG), and
  loading-status updates.

The wrapper is intentionally stateless — VX itself owns all state
(open files, current viewport, active analyses).

---

## Install

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate                       # macOS / Linux
# .venv\Scripts\activate                        # Windows PowerShell

pip install -r requirements.txt
```

See [`INSTALL.md`](INSTALL.md) for the full setup against Claude
Code / Claude Desktop, including the JSON snippet to drop into the
client's MCP configuration.

---

## Run

VX must already be running and listening on `127.0.0.1:9876`
(it does, by default, as soon as the GUI starts).

```bash
python vx_mcp_server.py
```

The server runs on stdio (the standard MCP transport); your MCP
client launches it as a child process.

Quick connectivity check (does NOT need the MCP server — talks
to VX directly):

```bash
curl -s http://127.0.0.1:9876/ping
# {"status":"ok","app":"VX Genome Viewer","api_version":2}
```

---

## Tool catalogue (high level)

The full list, including parameter shapes and return types, lives
in [`../api/openapi.yaml`](../api/openapi.yaml). Brief categories:

| Category | Tools | Examples |
|---|---|---|
| Observation | 5 | `vx_ping`, `vx_get_state`, `vx_screenshot`, `vx_list_chromosomes` |
| Navigation | 4 | `vx_navigate`, `vx_zoom`, `vx_pan`, `vx_select_region` |
| File loading | 1 | `vx_load_file` (auto-detects FASTA/GTF/BAM/BED/VCF/BigWig/etc.) |
| Track management | 4 | `vx_set_track_visibility`, `vx_set_track_height`, `vx_remove_track`, `vx_reorder_track` |
| Group management | 3 | `vx_create_group`, `vx_switch_group`, `vx_remove_group` |
| Data queries | 3 | `vx_get_sequence`, `vx_get_genes`, `vx_search_genes` |
| Export | 1 | `vx_export_region` |
| Bookmarks | 4 | `vx_add_bookmark`, `vx_list_bookmarks`, `vx_remove_bookmark`, `vx_goto_bookmark` |
| Loading status | 2 | `vx_loading_status`, `vx_cancel_loading` |
| Config | 1 | `vx_set_config` (grid, labels, dark mode, font/UI scale) |
| Analysis | 4 | `vx_list_analyses`, `vx_run_analysis`, `vx_analysis_status`, `vx_cancel_analysis` |
| Video recording | 3 | `vx_start_recording`, `vx_stop_recording`, `vx_recording_status` |
| Track display options | 4 | `vx_set_alignment_options`, `vx_set_signal_options`, `vx_set_variant_options`, `vx_set_interaction_options` |

---

## Privacy

The MCP server talks to `127.0.0.1` only. It does not make outbound
network calls of its own. VX itself only opens an outbound
connection if you explicitly invoke a reference-retrieval action
in the GUI (e.g. "fetch GRCh38 from UCSC"). See VX's
"Privacy & Usage Statistics" section in the main app's About
dialog for the per-feature breakdown.

---

## Versioning

The MCP server's tool list maps 1:1 to the VX HTTP API command
catalogue. The version of the server is pinned to the VX
release it ships with. If you upgrade VX, redeploy this folder's
contents to keep them in sync.

