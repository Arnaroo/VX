# VX MCP Server

`vx_mcp_server.py` is an [MCP](https://modelcontextprotocol.io)
server that exposes VX's HTTP API as a tool catalogue
for AI agents (Claude Code, Claude Desktop, and any other
MCP-compatible client).

**Licence:** MIT, see [`LICENSE`](LICENSE).

---

## What it does

VX runs an embedded HTTP API on `127.0.0.1:9876`. The MCP server
in this folder is a thin, dependency-light Python wrapper that:

- exposes 80 MCP tools to the agent: 75 send VX's commands through
  `POST /command` (`vx_load_demo` sends `load_demo`, or
  `demo_status` when no case is given; the four Edit mode tools
  send the 18 `edit_*` commands), `vx_navigate` posts to
  `/navigate`, and `vx_ping`, `vx_get_state`, `vx_screenshot` and
  `vx_screenshot_track` use the `GET` endpoints;
- translates MCP tool invocations into HTTP requests against the
  running VX instance;
- returns VX's JSON answers as text, an error's body included
  (whatever its HTTP status), and captures as MCP image blocks,
  which a vision model sees. A request VX gives no answer to (VX
  not running at the address in use, a wait that ends, a broken
  connection) is answered in the same shape, with `code`
  `CONNECTION_ERROR`, `CLIENT_TIMEOUT` or `HTTP_ERROR`.

The wrapper is intentionally stateless: VX itself owns all state
(open files, current viewport, active analyses). The commands
whose answer comes when their work ends (`next_coverage_region`,
`aggregate_rows`, `read_result_rows`, `load_demo` with case
`builtin`, `export_circular_view`, `dot_plot`) are awaited without
a client timeout.

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
(it does, by default, as soon as it starts; Settings > MCP / API).
For a VX on another port or address, set `VX_API_BASE` in the
server's environment (for example `http://127.0.0.1:9877`).

```bash
python vx_mcp_server.py          # stdio (the standard MCP transport)
python vx_mcp_server.py --sse    # SSE, for web clients
```

On stdio your MCP client launches the server as a child process.

Quick connectivity check (does NOT need the MCP server: talks
to VX directly):

```bash
curl -s http://127.0.0.1:9876/ping
# {"status":"ok","app":"VX","api_version":2}
```

---

## Tool catalogue (high level)

Each tool's docstring in [`vx_mcp_server.py`](vx_mcp_server.py) is
its reference; the HTTP shapes behind them are in
[`../api/openapi.yaml`](../api/openapi.yaml). Brief categories:

| Category | Tools | Examples |
|---|---|---|
| Observation | 5 | `vx_ping`, `vx_get_state`, `vx_screenshot`, `vx_screenshot_track`, `vx_list_chromosomes` |
| Navigation | 7 | `vx_navigate`, `vx_zoom`, `vx_pan`, `vx_select_region`, `vx_next_coverage_region`, `vx_cancel_coverage_scan`, `vx_click_element` |
| File & track management | 7 | `vx_load_file` (auto-detects FASTA/GTF/BAM/BED/VCF/BigWig/etc.), `vx_set_track_visibility`, `vx_set_track_height`, `vx_remove_track`, `vx_reorder_track`, `vx_set_track_scroll`, `vx_load_demo` |
| Group management | 4 | `vx_create_group`, `vx_switch_group`, `vx_remove_group`, `vx_set_reference_mode` |
| Data queries | 3 | `vx_get_sequence`, `vx_get_genes`, `vx_search_genes` |
| Configuration | 2 | `vx_set_config` (grid, labels, dark mode, font/UI scale, active mode, track height), `vx_set_magnifier` |
| Export & loading status | 6 | `vx_export_region`, `vx_export_image`, `vx_export_svg`, `vx_svg_export_status`, `vx_loading_status`, `vx_cancel_loading` |
| Bookmarks | 4 | `vx_add_bookmark`, `vx_list_bookmarks`, `vx_remove_bookmark`, `vx_goto_bookmark` |
| Track display options | 9 | `vx_set_track_options`, `vx_set_coverage_options`, `vx_set_signal_options`, `vx_set_variant_options`, `vx_set_interaction_options`, `vx_set_sequence_options`, `vx_set_gene_options`, `vx_set_feature_options`, `vx_set_alignment_options` |
| Read aggregates and transcript DTI | 6 | `vx_add_aggregate_track`, `vx_set_aggregate_options`, `vx_aggregate_rows`, `vx_add_dti_track`, `vx_set_dti_options`, `vx_dti_lookup` |
| Sashimi and overlay tracks | 4 | `vx_add_sashimi_track`, `vx_set_sashimi_options`, `vx_add_overlay_track`, `vx_set_overlay_options` |
| Analysis | 5 | `vx_list_analyses`, `vx_run_analysis`, `vx_analysis_status`, `vx_cancel_analysis`, `vx_read_result_rows` |
| Video recording | 3 | `vx_start_recording`, `vx_stop_recording`, `vx_recording_status` |
| Circular view and dot plot | 3 | `vx_open_circular_view`, `vx_export_circular_view`, `vx_dot_plot` |
| Sessions | 3 | `vx_save_session`, `vx_load_session`, `vx_shutdown` |
| Edit mode | 4 | `vx_edit_feature`, `vx_edit_bases`, `vx_edit_history`, `vx_edit_write` |
| Known Features | 5 | `vx_known_features`, `vx_known_features_status`, `vx_close_known_features`, `vx_export_known_features`, `vx_set_known_features_options` |

22 of the tools are new in 0.11.0: `vx_set_reference_mode`, the
track option tools other than those of the signal, variant,
interaction and alignment tracks, the Sashimi and overlay tools,
the circular view and dot plot tools, the Edit mode tools and the
Known Features tools.

---

## Privacy

The MCP server talks to VX's API only (`127.0.0.1:9876`, or the
address `VX_API_BASE` gives). It makes no other network call of
its own. For the network use of VX itself (opt-in usage
statistics, the downloads you ask for, the Known Features pane's
look-ups), see the main [README](../README.md) and the *Privacy &
Usage Statistics* section of VX's built-in manual (Settings >
Help).

---

## Versioning

The server's tools follow the VX release it comes with: this
folder is VX 0.11.0's (80 tools, over version 2 of the HTTP API).
If you upgrade VX, redeploy this folder's contents to keep them in
sync.
