# Changelog

User-visible changes to VX Genome Viewer. Newer entries are at the
top.

Detailed development history is maintained in private trackers;
this public changelog focuses on what changed in the binaries and
APIs between public releases.

---

## v0.9.0.1 — 2026-05-16 (archival re-publish)

Metadata-only release. No changes to binaries or APIs since
v0.9.0. This tag exists so that the public-facing repository is
captured in a Zenodo deposit and assigned a citable DOI for the
accompanying manuscript. README polish, per-path commit-message
tidy-up, and topic-tag listing committed since v0.9.0 are included
in the archived snapshot.

---

## v0.9.0 "Aardvark" — 2026-05-14 (first public pre-release)

First public-facing release. Triple-platform binaries (Linux,
macOS arm64, Windows x86_64) packaged from a single source tree.

### Added

- **Load-status strip** — a persistent UI strip showing file-open
  progress (parse phase) and per-region read-fetch progress. The
  strip never leaves the user wondering whether VX is busy or
  frozen.
- **Subsampling badge** — alignment tracks now overlay a small
  badge whenever the on-screen read set has been subsampled
  (capped by `max_reads`, default 500) so the user knows whether
  what they see is the full picture.
- **Asynchronous BAM loading** — region fetches no longer block
  the render thread. The viewport stays interactive while reads
  load in the background.
- **Analysis framework (Phases 1–4)** — 50+ computational
  analyses across signal math, sequence, quantification,
  interval operations, variant analysis, alignment stats, peak
  detection, interaction analysis, and cross-track correlation.
  Results land in a configurable `Results/` directory or, where
  appropriate, as a brand-new track.
- **Video recording** — capture the OpenGL viewport to MP4
  (H.264), WebM (VP9), or GIF. Configurable fps and capture
  mode (timer or per-frame). Uses ffmpeg via a piped raw-frame
  channel and PBO-backed GL readback.
- **MCP catalogue (43 tools)** — exposed via `mcp/vx_mcp_server.py`
  and reachable directly over HTTP on `127.0.0.1:9876`. Covers
  observation, navigation, file loading, track management,
  group management, data queries, export, bookmarks, loading
  status, runtime configuration, analysis dispatch, video
  recording, and per-track-type display options.
- **Magnifier popup** — Alt + hover over the viewport to open a
  rounded magnified inset (1.5×–10×).
- **Active mode** — Click any rendered element (gene, exon,
  read, variant, signal bin) to surface metadata in a
  pinnable side panel.
- **Bookmarks** — Name + revisit specific regions; persisted in
  the session file.
- **Sessions** — Save/load full UI + track state to a `.vxs`
  JSON file.
- **Triple-platform release profiles**:
  - Linux: `release-aggressive` (x86-64-v3 baseline),
    `release-znver2` (AMD Zen2), `release-broadwell`
    (Intel Broadwell), `release-native` (build-host CPU).
  - macOS: arm64 `.app` + `.dmg`, ad-hoc signed, relocatable.
  - Windows: x86_64 ZIP + Inno Setup `.exe` installer.

### Changed

- Release builds now use full LTO + static druntime/phobos
  on Linux. The narrowed `gtk-d:gtkd` dependency drops unused
  peas/vte/gstreamer/sv subpackages that previously caused a
  `libpeas-1.0.so.0` runtime-dlopen() to fail on hosts that
  only ship `libpeas-1.0.so.1`.
- All release-profile binaries are ≤ 19 MB on Linux.

### Known limitations

- **First-region BAM fetch on very large BAMs** (≈ 23 GB) may
  take ~2 minutes the first time you navigate into a chromosome.
  The load-status strip surfaces this; the underlying root-cause
  fix is deferred. Subsequent regions on the same chromosome are
  fast.
- **macOS GUI smoke test on real Apple Silicon hardware**: the
  binary builds, the HTTP API has been confirmed, but full-GUI
  visual confirmation on a real M1/M2/M3 Mac is pending. (The
  available CI VM tier uses a software OpenGL renderer that
  cannot compile our GLSL 130/330 shaders.)
- **Subsampling cap**: when more than 500 reads (default) fall in
  the visible window, only a uniform subsample is shown. Increase
  `max_reads` via the alignment-track options panel or the
  `vx_set_alignment_options` MCP tool to see more.

### Not included

- Source code. The VX D source remains proprietary; this
  repository ships only the redistributable artefacts. See the
  [main README](README.md) for the per-folder licensing matrix.

---

## Pre-public history

v0.9.0 is the first version exposed to the public, but it
inherits roughly 18 months of internal iteration. The pre-public
development history is maintained in private issue trackers and
is not included in this changelog. Selected highlights of recent
work that shapes the v0.9.0 user experience:

- **2026-05-14** — Release-profile unification: full LTO with
  static druntime/phobos, narrowed gtk-d subpackage dependency.
- **2026-05-14** — Load-status strip + subsampling badge landed.
  macOS bundle rebuilt for the unified release profile.
- **2026-05-13** — Async BAM loading: render thread no longer
  blocks on region fetches.
- **2026-05-13** — Read sort + CIGAR coverage optimisation for
  very large alignment regions.
- **2026-04-25** — Background-analysis status bar,
  drag-and-drop track reorder, borderless-window edge-resize fix.

---

## Citation

If you use VX in research, please see the citation block in the
[main README](README.md). DOI to follow on manuscript
publication.

