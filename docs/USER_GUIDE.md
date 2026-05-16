# VX Genome Viewer — User Guide

This guide walks through the most common workflows in VX. For a
quick reference, see [`KEYBOARD_SHORTCUTS.md`](KEYBOARD_SHORTCUTS.md);
for input/output formats, see [`FILE_FORMATS.md`](FILE_FORMATS.md);
for things that have gone wrong before, see
[`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).

---

## 1. The main window

After launching VX, you'll see:

- **Top header bar** — file open button, region search, zoom
  controls, the **Analyse** button (right of the search entry),
  and the settings menu.
- **Left panel** — chromosome list, bookmarks, group switcher,
  and (when collapsed) a slim handle. Toggle with **F9**.
- **Track panel (centre-left)** — list of currently displayed
  tracks with per-track visibility / height / options /
  selection-for-analysis checkboxes.
- **Viewport (centre-right)** — the OpenGL rendering surface.
- **Load-status strip (bottom)** — shows file-parse phase or
  per-region read-fetch progress whenever something is loading.

![VX main window](screenshots/07_multi_track.png)

---

## 2. Opening data

VX auto-detects file types by extension. Drop a file via the
header-bar open button, or via the `vx_load_file` MCP tool, or
on the command line:

```bash
./bin/genome-viewer my_reference.fa annotations.gtf reads.bam
```

The first FASTA you open creates a new **group**. Subsequent
annotation / alignment / signal / variant files attach to the
group whose reference they're consistent with (matched by
chromosome names via the alias resolver).

See [`FILE_FORMATS.md`](FILE_FORMATS.md) for the full list of
supported formats.

---

## 3. Navigating

- **Pan**: drag the viewport with the left mouse button, or use
  the arrow keys.
- **Zoom**: scroll wheel, or `Ctrl++` / `Ctrl+-`, or the zoom
  control in the header bar.
- **Zoom to fit**: `Ctrl+0`.
- **Region search**: type a chromosome (`chr1`) or region
  (`chr1:1000000-1500000`) or gene symbol (`BRCA1`) in the
  header search box.
- **Bookmarks**: `Ctrl+B` to add the current region as a
  bookmark; `Ctrl+]` / `Ctrl+[` to step through saved bookmarks.

VX changes what it draws based on zoom level (Level Of Detail).
Wider views show chromosome / gene-boundary outlines; narrower
views progressively reveal exon structure, then individual
base-pair text.

![Gene-boundary LOD](screenshots/02_gene_boundaries.png)
![Exon detail LOD](screenshots/04_exon_detail.png)
![Base level LOD](screenshots/05_base_level.png)

---

## 4. Working with tracks

Each track in the track panel has:

- A **visibility** toggle.
- A **height** slider.
- An **options** popover (right-click or three-dots menu) —
  alignment colouring, signal y-range, variant filters, etc.
- A **selection checkbox** for analysis input.

**Reorder tracks** by drag-and-drop within the panel. A drop
indicator line shows where the dropped track will land.

### Subsampling badge

Alignment tracks display a small badge in the top-right corner
when the number of overlapping reads in the visible window
exceeds `max_reads` (default: 500). Raise `max_reads` via the
track's options popover or via `vx_set_alignment_options` if you
need to see the full pile-up.

---

## 5. Active mode

Press `Ctrl+I` (or click the magnifying-glass icon in the
header) to enter Active Mode. Clicking a gene, exon, read,
variant, or signal bin opens a pinnable details panel with the
full metadata for that element. Click the pin to keep the panel
open while you keep navigating.

---

## 6. Magnifier popup

Hold `Alt` and hover the viewport. A rounded magnified inset
opens at the cursor (1.5×–10×, default 3×). Tap `+` / `-` or
`Alt+scroll` to adjust the zoom factor.

---

## 7. Dark mode

Toggle with `Ctrl+D`, or via Settings → Appearance.

![Dark mode](screenshots/06_dark_mode.png)

---

## 8. Sessions

Sessions persist the open files, viewport, track layout, and
bookmarks. `Ctrl+S` saves; `Ctrl+Shift+O` loads. Session files
are JSON (`.vxs`) — diff-able and re-openable on any platform.

---

## 9. Snapshots and video

- **Snapshot**: `Ctrl+Shift+E` exports the current viewport as
  PNG/JPEG/TIFF at a configurable scale factor.
- **Video recording**: `Ctrl+Shift+R` toggles. Choose MP4
  (H.264), WebM (VP9), or GIF; pick fps and capture mode
  (timer or per-frame). Requires `ffmpeg` on `PATH`.

---

## 10. Analysis framework

Tick the analysis selection checkboxes on the tracks you want as
inputs, then click **Analyse**. The popover lists every
applicable analysis based on your current selection (e.g.
**FeatureCounts** appears only when you have ≥1 gene track and
≥1 alignment track selected).

Results land in:

- a new track (when the analysis produces interval / signal /
  variant data), and/or
- a file in the configured `Results/` directory (BED, BedGraph,
  TSV depending on the analysis).

Long-running analyses run in the background; the status strip
shows progress and you can cancel.

The 50+ available analyses span signal math, sequence analysis,
quantification (RPKM/TPM/CPM), interval operations, variant
analysis, alignment stats, peak detection, interaction analysis,
and cross-track correlation. The popover's text labels and
tooltips are the canonical short descriptions.

---

## 11. Driving VX from an AI agent

The embedded HTTP API on `127.0.0.1:9876` lets agents (e.g.
Claude via the [VX MCP server](../mcp/README.md)) drive VX
programmatically — navigate, load files, run analyses, capture
screenshots, record video. See [`../api/`](../api/) and
[`../mcp/`](../mcp/) for the full spec.

---

## 12. Settings

Settings → Hotkeys lets you rebind every shortcut.
Settings → Appearance covers grid lines, label visibility, dark
mode, font scale, and UI scale.
Settings → Privacy controls the optional anonymous usage-stats
opt-in (default: off).

The configuration file lives next to the executable as
`genome-viewer.cfg` (INI format).

