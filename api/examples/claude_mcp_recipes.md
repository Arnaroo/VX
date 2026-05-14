# Claude MCP recipes for VX

Common agent-driven workflows using the [VX MCP server](../../mcp/).
Each recipe lists the underlying tool calls; Claude (or any other MCP
client) issues them in sequence. Tool names are 1:1 with HTTP commands
described in [`../openapi.yaml`](../openapi.yaml), prefixed with `vx_`.

These assume:

1. VX is open (`bin/genome-viewer` running).
2. The MCP server is registered with the client
   (`mcp/.venv/bin/python mcp/vx_mcp_server.py`).
3. A reference + relevant annotation tracks are already loaded.

If any of those is false, the first action is always
`vx_load_file(path="/abs/path/to/...")`.

---

## Recipe 1 — Inspect a gene and capture a publication-quality figure

Use case: "Show me the BRCA1 locus in the loaded genome and capture
a 4× resolution PNG for a figure."

1. `vx_search_genes(query="BRCA1")` → returns `chr17:43044295-43125483`
2. `vx_navigate(chromosome="chr17", start=43044295, end=43125483)`
3. `vx_set_config(dark_mode=False, show_grid=True, show_labels=True)`
4. `vx_screenshot(target="viewport", scale=4.0)` → high-resolution PNG
   returned as base64 in the tool result, suitable for direct paste
   into a manuscript.

---

## Recipe 2 — Walk a track of interest, region by region

Use case: "Find each region where the coverage track exceeds 30× and
take a screenshot of each one."

1. `vx_get_state()` → confirm a coverage track is visible.
2. `vx_next_coverage_region(direction="next", threshold=30.0)`
3. Inspect the returned `viewStart` / `viewEnd`.
   If `moved=false`, the walk is finished.
4. `vx_screenshot(target="viewport")`
5. Loop to step 2 until `moved=false`.

This mirrors the `«` / `»` buttons in the VX left control panel.

---

## Recipe 3 — Background analysis with progress polling

Use case: "Run a GC-content analysis on chromosome 17 and save the
output BedGraph next to the FASTA."

1. `vx_list_analyses(tracks=["chr17_seq"])` → confirm `GCContent`
   appears in the catalogue.
2. `vx_run_analysis(analysis="GCContent",
                    tracks=["chr17_seq"],
                    params={"scope": "chromosome",
                            "chromosome": "17",
                            "window_size": "100"},
                    output_path="/abs/path/out/chr17_gc.bedgraph")`
3. Poll: `vx_analysis_status()` every 1–2 s. Watch for `complete=true`.
4. On completion, the analysis output is also automatically loaded
   into a new BedGraph track — `vx_get_state()` will show it. Inspect
   it with `vx_screenshot_track(track_name="GC content (chr17 100bp)")`.

---

## Recipe 4 — Subsample-aware alignment inspection

Use case: "Open this 23 GB BAM and look at chr1:1000000-1010000.
Confirm subsampling did/didn't kick in."

1. `vx_load_file(path="/abs/path/sample.bam")`
   (the BAM auto-loads asynchronously — `vx_loading_status` until done)
2. `vx_navigate(chromosome="chr1", start=1000000, end=1010000)`
3. `vx_get_state()` — inspect the alignment track entry. The state
   tracks list does not encode the subsampling flag directly, but the
   alignment track itself draws a "Subsampled: N/M reads" badge in the
   label area when the read cap is hit.
4. `vx_screenshot_track(track_name="sample.bam")` — the screenshot
   includes the label area + badge.
5. If you want to override the cap, that requires editing
   `genome-viewer.cfg` (`max_reads`, `min_mapq` keys) and restarting VX;
   there is no live runtime command for it as of v0.9.0.

---

## Recipe 5 — Bookmark-driven tour

Use case: "Visit each of my saved bookmarks in turn and screenshot
the viewport at each one."

1. `vx_list_bookmarks()` → array of `{index, label, region}` entries.
2. For each `i` in the returned indices:
   - `vx_goto_bookmark(index=i)`
   - `vx_screenshot(target="viewport", scale=2.0)` → save the bytes
     under `<label>.png`.

---

## Recipe 6 — Drive an SVG export for figure layout

Use case: "Export the current viewport as a vector graphic I can
edit in Illustrator/Inkscape."

1. `vx_navigate(...)` to position the viewport.
2. `vx_export_svg(path="/abs/path/figure_1.svg",
                  include_ruler=True, include_grid=False,
                  include_labels=True, dark_mode=False,
                  font_family="Helvetica")`
3. Poll: `vx_svg_export_status()` until `status="complete"`.
4. The file is now at `/abs/path/figure_1.svg`.

SVG export runs on a background thread, so step 3 is essential.

---

## Recipe 7 — Record a navigation animation as video

Use case: "Record a 10-second sweep across chr1:1-100000000 as MP4."

1. `vx_recording_status()` → confirm `ffmpeg_available=true`. If not,
   surface the install hint to the user and stop.
2. `vx_start_recording(format="mp4", fps=30, capture_mode="timer",
                       quality=23,
                       output_path="/abs/path/out")`
3. Drive a navigation sweep — repeated `vx_pan(offset=...)` or
   `vx_navigate(...)` calls.
4. `vx_stop_recording()` → returns the output file path and frame count.

`capture_mode="render"` instead records exactly one video frame per
GL repaint (useful for jerky / on-demand animations); the default
`"timer"` mode samples at the requested FPS regardless of activity.

---

## Error handling pattern

Every MCP tool returns a JSON string. On failure, parse it and check
for `code`:

```python
import json
r = json.loads(vx_navigate(chromosome="chrZ", start=0, end=1))
if "code" in r:
    if r["code"] == "NOT_FOUND":
        # chromosome doesn't exist in the loaded reference
        chroms = json.loads(vx_list_chromosomes())
        # ... recover or surface to the user ...
    elif r["code"] == "NOT_READY":
        # VX hasn't finished startup yet
        time.sleep(1)
        # retry
```

The full set of error codes is listed in [`../README.md`](../README.md).
