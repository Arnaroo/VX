# Claude MCP recipes for VX

Common agent-driven workflows using the [VX MCP server](../../mcp/).
Each recipe lists the underlying tool calls; Claude (or any other MCP
client) issues them in sequence. Most tool names are the HTTP commands
described in [`../openapi.yaml`](../openapi.yaml) with a `vx_` prefix;
[`../README.md`](../README.md) lists the exceptions.

These assume:

1. VX is open (`bin/vx` running).
2. The MCP server is registered with the client
   (`mcp/.venv/bin/python mcp/vx_mcp_server.py`).
3. A reference + relevant annotation tracks are already loaded.

If any of those is false, the first action is always
`vx_load_file(path="/abs/path/to/...")`, or
`vx_load_demo(case="3b")` to try VX on a demo dataset.

---

## Recipe 1: Inspect a gene and capture a publication-quality figure

Use case: "Show me the BRCA1 locus in the loaded genome and capture
a 4× resolution PNG for a figure."

1. `vx_search_genes(query="BRCA1")` → returns the gene's chromosome,
   start and end (e.g. `chr17:43044295-43125483`)
2. `vx_navigate(chromosome="chr17", start=43044295, end=43125483)`
3. `vx_set_config(dark_mode=False, show_grid=True, show_labels=True)`
4. `vx_screenshot(target="viewport", scale=4.0)` → a high-resolution
   PNG, returned as an image the model sees. For a file to paste into
   a manuscript, `vx_export_image(path="/abs/path/brca1.png", scale=4.0)`
   writes it.

---

## Recipe 2: Walk a track of interest, region by region

Use case: "Find each region where the coverage track exceeds 30× and
take a screenshot of each one."

1. `vx_get_state()` → confirm a coverage, alignment or signal track
   is visible.
2. `vx_next_coverage_region(direction="next", threshold=30.0)` (it
   answers when its scan ends, which on a whole chromosome of a large
   BAM can take a minute or more)
3. Inspect the returned `targetStart` / `targetEnd` and `viewStart` /
   `viewEnd`. If `moved=false`, the walk is finished.
4. `vx_screenshot(target="viewport")`
5. Loop to step 2 until `moved=false`.

This mirrors the `«` / `»` buttons in the VX left control panel.

---

## Recipe 3: Background analysis with progress polling

Use case: "Run a GC-content analysis on chromosome 17 and save the
output bedGraph next to the FASTA."

1. `vx_list_analyses()` → confirm `GCContent` appears in the
   catalogue for the loaded tracks.
2. `vx_run_analysis(analysis="GCContent",
                    params={"chromosome": "17",
                            "window_size": "100"},
                    output_path="/abs/path/out/chr17_gc.bedgraph")`
   (`chromosome` alone names the whole chromosome; without it the
   analysis runs on the view)
3. Poll: `vx_analysis_status()` every 1 to 2 s. Watch for
   `complete=true`, then read `success`, `output_path` and `summary`.
4. The result is also added as a new track (Settings > Analysis
   decides; on by default): `vx_get_state()` names it, and
   `vx_screenshot_track(track_name=<that name>)` captures it.
   `vx_read_result_rows(path=<output_path>)` gives the file's rows a
   page at a time.

---

## Recipe 4: Subsample-aware alignment inspection

Use case: "Open this 23 GB BAM and look at chr1:1000000-1010000.
Confirm subsampling did/didn't kick in."

1. `vx_load_file(path="/abs/path/sample.bam")`
   (the BAM auto-loads asynchronously: `vx_loading_status` until
   `done` is true, `finalizing` false and `queued` 0)
2. `vx_navigate(chromosome="chr1", start=1000000, end=1010000)`
3. `vx_set_alignment_options(name="sample.bam")`: with the name
   alone it changes nothing and answers the track's `options`, among
   them `max_reads`, `reads_loaded` and `reads_before_subsampling`.
   The track itself draws a `kept/total` badge in its label column
   when the cap is hit.
4. `vx_screenshot_track(track_name="sample.bam")`: the screenshot
   includes the label area + badge.
5. To raise the cap: `vx_set_alignment_options(name="sample.bam",
   max_reads=5000)` (0: no cap; or `subsetting=False`); the view
   loads again.

---

## Recipe 5: Bookmark-driven tour

Use case: "Visit each of my saved bookmarks in turn and screenshot
the viewport at each one."

1. `vx_list_bookmarks()` → array of `{index, label, region}` entries.
2. For each `i` in the returned indices:
   - `vx_goto_bookmark(index=i)`
   - `vx_screenshot(target="viewport", scale=2.0)` → save the image
     under `<label>.png`.

---

## Recipe 6: Drive an SVG export for figure layout

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

## Recipe 7: Record a navigation animation as video

Use case: "Record a 10-second sweep across chr1:1-100000000 as MP4."

1. `vx_recording_status()` → confirm `ffmpeg_available=true`. If not,
   surface the install hint to the user and stop.
2. `vx_start_recording(format="mp4", fps=30, capture_mode="timer",
                       quality=23,
                       output_path="/abs/path/out")`
3. Drive a navigation sweep: repeated `vx_pan(offset=...)` or
   `vx_navigate(...)` calls.
4. `vx_stop_recording()` → returns the output file path and frame count.

`capture_mode="render"` instead records exactly one video frame per
GL repaint (useful for jerky / on-demand animations); the default
`"timer"` mode samples at the requested FPS regardless of activity.

---

## Error handling pattern

Every MCP tool returns a JSON string, an error's body included. On
failure, parse it and check for `code`:

```python
import json
import time
r = json.loads(vx_goto_bookmark(index=99))
if "code" in r:
    if r["code"] == "NOT_FOUND":
        # there is no bookmark of that index
        bookmarks = json.loads(vx_list_bookmarks())
        # ... recover or surface to the user ...
    elif r["code"] == "NOT_READY":
        # VX cannot serve it yet (still starting, or nothing loaded)
        time.sleep(1)
        # retry
```

The full set of error codes, with the HTTP status of each, is listed
in [`../README.md`](../README.md).
