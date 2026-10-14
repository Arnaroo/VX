# VX: User Guide

This guide walks through the most common workflows in VX. For a
quick reference, see [`KEYBOARD_SHORTCUTS.md`](KEYBOARD_SHORTCUTS.md);
for input/output formats, see [`FILE_FORMATS.md`](FILE_FORMATS.md);
for things that have gone wrong before, see
[`TROUBLESHOOTING.md`](TROUBLESHOOTING.md). The complete manual
is the README inside VX (Settings > Help).

---

## 1. The main window

After launching VX, you'll see:

- **Header bar** (top): the **Open** menu (a reference genome,
  annotations, a track, the recognised files of a directory, a
  demo dataset), Load Session and Save Session, two arrows that
  move the view half its width left or right, the search entry
  (a region or a gene), the **Analyse** button, Settings, the
  interface scale (minus, 100%, plus) and the Active Mode switch.
  On Linux and Windows VX draws its own window buttons there; on
  macOS the system's title bar holds them.
- **Toolbar** (below it): snapshot, SVG export and recording;
  zoom out, fit and zoom in; moving the selected track up or
  down; track height, text scale and track scale; the switches
  for gene detail, intron collapse, chromosome bands and the grid.
- **Left panel**: *Reference Groups* (the active group, Load
  Reference, Retrieve Reference), then two pages: **Controls**
  (the chromosome and its aliases, start and end, the coverage
  navigation, zoom, Quick Navigation with the bookmarks, the
  loaded data) and **Tracks** (the track panel). Toggle the
  panel with **F9**.
- **Viewport** (centre): the OpenGL drawing area, with the
  chromosome's overview bar and the ruler above the tracks.
- **Load-status strip** (bottom of the viewport): what is loading
  (a file, a region's reads), its progress, and whether it ended
  or failed.
- **Status bar** (bottom of the window): messages, the progress of
  analyses, and a counter of errors and warnings when there are
  any.

![VX main window (VX 0.9.0)](screenshots/07_multi_track.png)

---

## 2. Opening data

VX recognises a file by its extension. Open one from the header
bar's **Open** menu, with **Load Reference** in the left panel (a
FASTA), with `Ctrl+O` (a reference genome), through the API's
`load_file` command (the MCP tool `vx_load_file`), or at start
with `--load`, once per file, in order:

```bash
./bin/vx --load my_reference.fa --load annotations.gtf --load reads.bam
```

**Open > Open Demo Dataset** downloads one of the demo datasets
once, checks it, and opens it at the view of its figure.

A reference FASTA creates a new **group**. Annotation, alignment,
signal, variant and interaction files are added to the **active
group**: switch groups in the left panel's *Reference Groups*.
Chromosome names are matched between files that write them
differently (`chr1`, `1`, `NC_000001.11`) by an alias resolver.

See [`FILE_FORMATS.md`](FILE_FORMATS.md) for the full list of
supported formats.

---

## 3. Navigating

- **Pan**: scroll the mouse wheel, drag the viewport, or use the
  left and right arrow keys.
- **Zoom**: `Ctrl` (Command on macOS) with the scroll wheel, `Ctrl++` / `Ctrl+-`, or
  the zoom buttons of the toolbar.
- **Zoom to fit**: `Ctrl+0` shows the whole chromosome; `W` (and
  the toolbar's fit button) fits the selection, else the largest
  gene or feature in view, else the chromosome.
- **Region search**: type a region (`chr1:1000000-1500000`) or a
  gene name (`BRCA1`) in the header's search entry; `Ctrl+F`
  puts the cursor there.
- **Bookmarks**: `Ctrl+B` bookmarks the view, and the left
  panel's *+ Bookmark Current View* the selection, else the view
  (both once a reference is loaded); `Ctrl+]` / `Ctrl+[` step
  through the bookmarks, which the left panel's Quick Navigation
  lists.
- **Coverage**: the « and » buttons beside *Cov ≥* in the left
  panel go to the previous or next region whose coverage reaches
  the threshold.
- **Overview**: click or drag the rectangle in the overview bar.

VX changes what it draws with the zoom (its levels of detail).
Wide views show gene density, then gene outlines; narrower views
show exon structure, then single bases.

![Gene level](screenshots/03_gene_detail.png)
![Exon level](screenshots/04_exon_detail.png)
![Base level](screenshots/05_base_level.png)

---

## 4. Working with tracks

The **Tracks** page of the left panel lists the tracks of the
active group. Each row has:

- a **drag handle**: drag a row to reorder the tracks; a line
  shows where the track will land;
- a **selection checkbox** that makes the track an analysis input;
- a **visibility** switch;
- a **settings** button: the options of the track's type (an
  alignment track's reads, read layout, marks and strips; a
  signal track's style and scale; a variant track's display and
  filters; and every track's colours and height);
- a **remove** button.

The toolbar's up and down buttons move the selected track, and
its *Height* sets the selected tracks' height.

### Subsampling badge

When an alignment track holds fewer reads than the view has (its
*Max reads* cap, 500 by default), a badge in the track's label
column shows `kept/total` (for example `500/3.2k`). Raise the cap
in the track's settings (Reads) or with
`vx_set_alignment_options(name=..., max_reads=...)`; the view then
loads again.

---

## 5. Active mode

Press `Ctrl+I` (or turn on the *Active* switch in the header bar)
to enter Active Mode:

- **Hover** highlights an element and shows its details.
- **Click** selects it; `Ctrl`+click (Command+click on macOS) adds to the selection.
- **Right-click** on a read or a modification mark shows its
  information; on a selected read it opens the read's menu (copy
  the CIGAR, the name or the sequence, other alignments, aggregate
  tracks).
- **Drag** makes a region with its statistics (mean, minimum,
  maximum, sum); `Shift`+click places a coordinate cursor and
  `Shift`+drag defines a region.

The information popup has **Copy** and **Save TSV** buttons.

---

## 6. Magnifier popup

Hold `Alt` and hover the viewport. A rounded magnified inset
opens at the cursor (1.5× to 10×, default 3×). While `Alt` is
held, `+` (or `=`) and `-` change the magnification, as does
`Alt`+scroll. Settings > Output > Viewport sets it up.

---

## 7. Dark mode

Toggle with `Ctrl+D`, or in Settings > Appearance > Display. At
the first start VX takes the desktop's dark preference; from then
on the scheme is VX's own setting. The tracks, the ruler, the
overview, the popups, the window's controls, its dialogs and the
status bar all take it; an SVG export can be drawn in the dark
scheme too (Settings > Output > Capture).

---

## 8. Sessions

A session holds the view, the display settings, every reference
group with its tracks and their settings, the tracks made by
analyses with their result files, and the bookmarks. `Ctrl+S`
saves; `Ctrl+Shift+O` loads; Settings > Startup can load the last
session at start. Session files are JSON (`.vxs`). Track data is
not in the file: each track is loaded again from its file by its
path, so a session can be shared with the data it names; when a
file is missing, VX offers to skip it or to locate it.

---

## 9. Snapshots and video

- **Snapshot**: `Ctrl+Shift+E` exports the viewport as PNG, JPEG
  or TIFF at the scale set in Settings > Output > Capture;
  `Ctrl+Shift+V` exports it as SVG.
- **Video recording**: `Ctrl+Shift+R` starts and stops it. Choose
  MP4 (H.264), WebM (VP9) or GIF, the frame rate and the capture
  mode (timer: a fixed frame rate; render: every frame drawn) in
  Settings > Output > Capture. Requires `ffmpeg` on `PATH`.

---

## 10. Analysis framework

Tick the analysis selection checkboxes on the tracks you want as
inputs, then click **Analyse**. The popover lists the analyses
those tracks can take (for example, Feature Counts appears when
an alignment track and a gene track are among them); the run
dialog chooses where the analysis runs (the view, the chromosome
in view, or every chromosome of its inputs).

Each result is a file in the results directory (Settings > Paths;
`Results` beside the program by default, on macOS in
`~/Library/Application Support/VX/`): BED, bedGraph or TSV, with a
manifest beside it that records the inputs, the parameters as
applied and the region. A BED or bedGraph result is also added as
a track (Settings > Analysis).

Analyses run in the background; the status bar shows their
progress: a click on a running analysis cancels it, a click on a
finished one opens its file, and a right click offers its details.

The 49 analyses span signal math, sequence analysis,
quantification (RPKM/TPM/CPM), interval operations, variant
analysis, alignment statistics, peak detection, interaction
analysis, and cross-track correlation. The popover's text labels
and tooltips are the canonical short descriptions.

---

## 11. Driving VX from an AI agent

The embedded HTTP API on `127.0.0.1:9876` lets agents (e.g.
Claude via the [VX MCP server](../mcp/README.md)) drive VX
programmatically: navigate, load files, run analyses and read
their result files, capture images, record video. See
[`../api/`](../api/) and [`../mcp/`](../mcp/) for the full spec.

---

## 12. Settings

Settings (`Ctrl+,`) has 13 tabs. Settings > Hotkeys rebinds the
shortcuts. Settings > Appearance > Display covers the interface
and font scale, dark mode, the grid, the labels and Active Mode.
Settings > Paths sets the reference, results, sessions and tracks
directories and shows this run's log file. Settings > Privacy
holds the optional anonymous usage statistics (off by default).

The configuration file is `vx.cfg` (INI format), next to the
executable; on macOS it is in `~/Library/Application Support/VX/`.
