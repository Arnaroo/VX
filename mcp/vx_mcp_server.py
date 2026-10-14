#!/usr/bin/env python3
"""
VX: MCP Server

Exposes VX's embedded HTTP API as Claude-compatible MCP tools (58 tools).
Requires the VX application to be running with its API server on port 9876, or at the address the
environment variable VX_API_BASE gives (for example http://127.0.0.1:9911, for a second viewer).

Since 0.10.0 an error answer of the API carries its HTTP status (400 for a request the
client can mend, 403 for a path vx_read_result_rows does not read, 404 for a name that is
not there, 405 for a method the API does not take, 409 for a state the request conflicts
with, 501 not implemented, 503 when the viewer cannot serve it now, 504 when the window did
not answer in time or a coverage scan stalled, 500 otherwise) with the
same JSON body as before: `error`, `code` and, where there is one, `details`. Every tool
returns that body as its text, whatever the status; nothing is raised on the status alone.
The API sends no CORS header and answers OPTIONS with 405: a page in a browser cannot drive it.

Usage:
  python vx_mcp_server.py          # stdio mode (for Claude Code)
  python vx_mcp_server.py --sse    # SSE mode (for web clients)
"""

import base64
import json
import os
import sys
import urllib.parse
from typing import Any

import httpx
from fastmcp import FastMCP
from mcp.types import ImageContent, TextContent

VX_API_BASE = os.environ.get("VX_API_BASE", "http://127.0.0.1:9876").rstrip("/")   # the viewer's API
TIMEOUT = 30.0  # seconds (longer for file loading)

mcp = FastMCP("VX")


# ─── HTTP helpers ───────────────────────────────────────────────────────


def _vx_get(path: str, **kwargs) -> httpx.Response:
    """GET request to VX API. The answer is returned whatever its status: since 0.10.0 an
    error answer carries a 4xx or 5xx status with its JSON body, and the caller reads the body."""
    try:
        return httpx.get(f"{VX_API_BASE}{path}", timeout=TIMEOUT, **kwargs)
    except httpx.ConnectError:
        raise RuntimeError(
            "[CONNECTION_ERROR] Cannot connect to VX. Is VX running? "
            "The API server should be listening on 127.0.0.1:9876."
        )


def _vx_post(path: str, data: dict, timeout=TIMEOUT) -> httpx.Response:
    """POST request to VX API. The answer is returned whatever its status (see _vx_get); timeout=None
    waits for as long as the viewer takes (a command whose answer comes when its work ends)."""
    try:
        return httpx.post(f"{VX_API_BASE}{path}", json=data, timeout=timeout)
    except httpx.ConnectError:
        raise RuntimeError(
            "[CONNECTION_ERROR] Cannot connect to VX. Is VX running? "
            "The API server should be listening on 127.0.0.1:9876."
        )


def _answer(r: httpx.Response) -> dict:
    """The JSON body of an answer, whatever its HTTP status. A body that is not JSON (there is
    none in the API; a proxy's page would be one) becomes an error dict naming the status."""
    try:
        body = r.json()
    except ValueError:
        return {"error": f"HTTP {r.status_code}: {r.text[:300]}", "code": f"HTTP_{r.status_code}"}
    if isinstance(body, dict):
        return body
    return {"result": body}


def _vx_cmd(command: str, **params) -> dict:
    """Send a command to VX via POST /command.

    Returns the parsed JSON response, whatever the HTTP status. Error responses include
    structured fields:
    - error: Human-readable error message
    - code: Machine-readable error code, which since 0.10.0 also sets the HTTP status:
            400 INVALID_PARAMS, PARSE_ERROR, UNKNOWN_ANALYSIS, NOT_SUPPORTED;
            403 NOT_A_RESULT (a path vx_read_result_rows does not read);
            404 UNKNOWN_COMMAND, NOT_FOUND, UNKNOWN_ENDPOINT; 405 METHOD_NOT_ALLOWED;
            409 INVALID_STATE, BUSY, NO_REFERENCE, NO_ANNOTATION; 501 NOT_IMPLEMENTED;
            503 NOT_READY, NO_RENDER; 504 STALLED (a coverage scan stopped by its bound), TIMEOUT (the
            window did not answer in time: the request
            may still be carried out, and its answer is not sent; ask for the state to see);
            500 OPERATION_FAILED, IO_ERROR, DEPENDENCY_MISSING, INTERNAL_ERROR and an error
            without a code
    - details: Optional additional context or remediation hints
    """
    r = _vx_post("/command", {"command": command, "params": params})
    return _answer(r)


# ═══════════════════════════════════════════════════════════════════════
# Phase 1 Tools (preserved)
# ═══════════════════════════════════════════════════════════════════════


@mcp.tool()
def vx_ping() -> str:
    """Check whether VX is running and the API is reachable."""
    r = _vx_get("/ping")
    return r.text


@mcp.tool()
def vx_get_state() -> str:
    """Get the full current state of VX.

    Returns JSON with:
    - chromosome, viewStart, viewEnd, viewLength, zoomLevel
    - activeGroup, tracks (name, type, visible, height; an interaction track's interaction: opacity as drawn in the
      scheme shown, customOpacity true when the user set it; a signal track's signal: source "file" or "memory",
      and window: the chromosome in view, the bounds held, zoomLevel (an index into the file's levels, or "raw"),
      stretches, basesPerPixel; null when the track has no such chromosome; a result track's result: analysis,
      analysisName, file, manifest, parameters; a feature track's feature: colour, the one its features are
      drawn in in the scheme shown (the scheme's for features without a colour of their own), customColour
      true when the user set it, fromAnnotation true for a file of features that holds no gene, fileColours
      true when every feature has a colour of its own, a BED's itemRgb)
    - chromosomes (name, length)
    - groups (name, type, isActive, trackCount)
    - config (interfaceScale, fontScale, showGrid, showLabels, darkMode, trackHeight)
    - windowWidth, windowHeight; viewportWidth, viewportHeight (the viewport's size in logical pixels) and
      scaleFactor (since 0.10.0)
    - each interaction track's tadBoundaries once TAD Boundary Detection has run on it: count, and boundaries
      with chromosome, start, end and strength (null when the analysis gave none)
    - each alignment track's readLayout gives hidden_all (every read of the view hidden by the filters) and the three
      class switches; totalMappedReads is the BAM index's count of mapped records; coverageReadTo is the last base
      (1-based) whose depth the coverage strip read whole when the view held more records than the read budget, the
      strip ending there, and null when the window was read whole (since 0.10.0)
    - results_reused, results_missing and results_status after a session load (the status also names what the
      restore did not make and why, since 0.10.0); restore_skipped, each part of the session not restored
      (group, track, reason); sessionRestoring (a restore is still applying its tracks' settings: wait for false
      before reading them; a restore with no file to load ends at once); headless (no window)
    """
    r = _vx_get("/state")
    return json.dumps(r.json(), indent=2)


@mcp.tool()
def vx_navigate(chromosome: str, start: int, end: int) -> str:
    """Navigate the VX viewer to a specific genomic region.

    Args:
        chromosome: Chromosome name (e.g. "chr1", "chrX", "1")
        start: Start position (0-based)
        end: End position (exclusive), must be > start
    """
    if end <= start:
        return json.dumps({"error": "end must be greater than start", "code": "INVALID_PARAMS",
                           "details": f"Got start={start}, end={end}. Provide 0-based coordinates with end > start."})
    r = _vx_post("/navigate", {"chromosome": chromosome, "start": start, "end": end})
    return r.text


@mcp.tool()
def vx_screenshot(target: str = "full", scale: float = 1.0) -> list[ImageContent | TextContent]:
    """Capture a screenshot of VX.

    Since 0.10.0 every capture is rendered, never read from the screen: a covered window,
    a screen saver or a locked screen cannot change the image. "full" draws the whole
    window (toolbar, panels and the track area) into an image at the scale asked for;
    the track area in it is what the window's OpenGL area last drew, so on a viewer
    without a display it is blank. "viewport" renders the track area alone off screen
    at the scale asked for, without the toolbar. Track names are drawn at rest (since 0.10.0),
    so two captures of one view are the same image.

    Args:
        target: "full" for the entire window, "viewport" for the track area alone
        scale: Resolution scale factor from 0.25 to 8 (1.0 = screen resolution, 2.0 = 2x);
               a scale outside that range is refused (INVALID_PARAMS, HTTP 400)

    Returns the image as a base64-encoded PNG (RGB, no alpha channel) suitable for vision
    models, or the error text: a capture that cannot be rendered (no window yet; no OpenGL
    context for the viewport, as on a viewer without a display) answers NO_RENDER (HTTP 503)
    with the reason in `details`. Since 0.10.0 the image is an MCP image block, which a vision
    model sees (it was a JSON text holding the base64, which no client shows as an image).
    """
    endpoint = "/screenshot/viewport" if target == "viewport" else "/screenshot"
    params = {}
    if scale != 1.0:
        params["scale"] = str(scale)
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        endpoint = f"{endpoint}?{qs}"
    r = _vx_get(endpoint)

    if r.headers.get("content-type", "").startswith("image/"):
        img_b64 = base64.b64encode(r.content).decode("ascii")
        scale_info = f", {scale}x" if scale != 1.0 else ""
        return [
            ImageContent(type="image", data=img_b64, mimeType="image/png"),
            TextContent(type="text", text=f"Screenshot captured ({target}{scale_info}, {len(r.content)} bytes)"),
        ]
    else:
        return [TextContent(type="text", text=f"Error: {r.text}")]


@mcp.tool()
def vx_screenshot_track(track_name: str, scale: float = 1.0) -> list[ImageContent | TextContent]:
    """Capture a screenshot of a single track from VX.

    Renders just the specified track (with its label area) to a PNG image
    using off-screen FBO rendering. Useful for examining individual tracks
    at high resolution. The track's name is drawn at rest (since 0.10.0), so two captures of
    one track in one view are the same image.

    Args:
        track_name: Name of the track to capture (as shown in vx_get_state tracks list); any
                    name is accepted (it is URL-encoded here, so spaces, '&' and '+' are safe)
        scale: Resolution scale factor from 0.25 to 8 (1.0 = screen, 2.0 = 2x); a scale
               outside that range is refused (INVALID_PARAMS, HTTP 400)

    Returns the image as a base64-encoded PNG (RGB, no alpha channel) suitable for vision
    models, or the error text: a track that is not among the visible tracks answers NOT_FOUND
    (HTTP 404); a viewer that cannot render (no OpenGL context, as without a display) answers
    NO_RENDER (HTTP 503) with the reason in `details`. Since 0.10.0 the image is an MCP image
    block, which a vision model sees (it was a JSON text holding the base64).
    """
    endpoint = f"/screenshot/track?name={urllib.parse.quote(track_name, safe='')}"
    if scale != 1.0:
        endpoint += f"&scale={scale}"
    r = _vx_get(endpoint)

    if r.headers.get("content-type", "").startswith("image/"):
        img_b64 = base64.b64encode(r.content).decode("ascii")
        scale_info = f", {scale}x" if scale != 1.0 else ""
        return [
            ImageContent(type="image", data=img_b64, mimeType="image/png"),
            TextContent(type="text", text=f"Track screenshot: {track_name}{scale_info} ({len(r.content)} bytes)"),
        ]
    else:
        return [TextContent(type="text", text=f"Error: {r.text}")]


# ═══════════════════════════════════════════════════════════════════════
# Phase 2 Tools: File Loading
# ═══════════════════════════════════════════════════════════════════════


@mcp.tool()
def vx_load_file(path: str) -> str:
    """Load a genomic file into VX. Auto-detects the file type. Any number of files can be loaded in
    a session (since 0.10.0).

    Supported formats:
    - Reference genomes: .fasta, .fa, .fna (a sequence line with a space or a tab before one of its
      bases is refused by name with its line number, whatever the file's size)
    - Annotations: .gtf, .gff, .gff3 (RefSeq GFF3, NCBI's gene- and rna- prefixes with partial=true,
      start_range or end_range, is grouped as Ensembl's, and a partial translated region's start reads
      as not found; a file over 50 MiB is read through a gene index saved beside it, format GDX7, an
      older index rebuilt once)
    - Tracks: .bam (alignments), .sam (read as a coverage track: each mapped record counts over its
      aligned bases, an intron's N not counted; since 0.10.0, before as an empty alignment track), .bed,
      .bedgraph, .wig, .bigwig
    - Signal: .bigwig, .bw (continuous signal data with indexed random access)
    - Variants: .vcf (SNPs, indels, structural variants)
    - Interactions: .bedpe (paired genomic interactions, Hi-C); an anchor written end first is read with its two numbers swapped, and one WARN line in the log counts them
    - Features: .bigbed, .bb (indexed binary BED)

    Loading a reference genome (.fasta) creates a new group.
    Annotations and tracks are added to the active group.

    The answer says what happened: "Loading <kind>: <name>" when the load starts now, or
    "Queued: <name> (position N)" when the file waits behind another load (since 0.10.0;
    poll vx_loading_status until done). A file that is not there answers NOT_FOUND (HTTP 404). A file that
    fails to load opens no dialog (since 0.10.0): vx_loading_status gives hasError, errorMessage (the reason,
    naming the file) and filename, and the log an ERROR line.

    Args:
        path: Absolute path to the file on the local filesystem
    """
    return json.dumps(_vx_cmd("load_file", path=path))


# ═══════════════════════════════════════════════════════════════════════
# Phase 2 Tools: Track Management
# ═══════════════════════════════════════════════════════════════════════


@mcp.tool()
def vx_set_track_visibility(name: str, visible: bool) -> str:
    """Show or hide a track by name.

    Args:
        name: Track name (as shown in vx_get_state)
        visible: True to show, False to hide
    """
    return json.dumps(_vx_cmd("set_track_visibility", name=name, visible=visible))


@mcp.tool()
def vx_set_track_height(name: str, height: float) -> str:
    """Change the display height of a track.

    Args:
        name: Track name
        height: Height in pixels (minimum 10, no upper limit)
    """
    return json.dumps(_vx_cmd("set_track_height", name=name, height=height))


@mcp.tool()
def vx_remove_track(name: str) -> str:
    """Remove a track from the active group.

    Args:
        name: Track name to remove
    """
    return json.dumps(_vx_cmd("remove_track", name=name))


@mcp.tool()
def vx_reorder_track(name: str, position: int) -> str:
    """Move a track to a new position in the display order.

    Args:
        name: Track name to move
        position: New 0-based position index
    """
    return json.dumps(_vx_cmd("reorder_track", name=name, position=position))


# ═══════════════════════════════════════════════════════════════════════
# Phase 2 Tools: Group Management
# ═══════════════════════════════════════════════════════════════════════


@mcp.tool()
def vx_create_group(name: str) -> str:
    """Create a new empty track group.

    Args:
        name: Name for the new group
    """
    return json.dumps(_vx_cmd("create_group", name=name))


@mcp.tool()
def vx_switch_group(name: str) -> str:
    """Switch to a different track group.

    Args:
        name: Name of the group to activate
    """
    return json.dumps(_vx_cmd("switch_group", name=name))


@mcp.tool()
def vx_remove_group(name: str) -> str:
    """Remove a track group.

    Args:
        name: Name of the group to remove
    """
    return json.dumps(_vx_cmd("remove_group", name=name))


# ═══════════════════════════════════════════════════════════════════════
# Phase 2 Tools: Navigation & Zoom
# ═══════════════════════════════════════════════════════════════════════


@mcp.tool()
def vx_zoom(factor: float) -> str:
    """Zoom the viewport in or out.

    Args:
        factor: Zoom factor. >1 zooms in (e.g. 2.0 = 2x closer),
                <1 zooms out (e.g. 0.5 = 2x wider view).
                The view range is divided by this factor.
    """
    return json.dumps(_vx_cmd("zoom", factor=factor))


@mcp.tool()
def vx_pan(offset: int) -> str:
    """Pan the viewport left or right by a genomic offset.

    Args:
        offset: Number of bases to shift. Positive = right, negative = left.
    """
    return json.dumps(_vx_cmd("pan", offset=offset))


@mcp.tool()
def vx_next_coverage_region(direction: str = "next", threshold: float = -1.0, track: str = "") -> str:
    """Jump to the next or previous coverage region above a threshold.

    Mirrors the « / » buttons in VX's left control panel. Scans one track's coverage on the chromosome
    in view, every base: the track named; else the first visible coverage track; else the first visible
    alignment track (its BAM's depth) or signal track (bedGraph, Wiggle, BigWig), top to bottom. Next
    goes to the first base of the next region whose coverage meets the threshold (a region the view's
    right edge is inside is passed over), previous to the last base of the previous region; that base is
    placed a quarter of the view from its left edge. The scan runs beside the window, which keeps
    drawing and answering other calls; this call returns when the scan ends, which on a whole chromosome
    of a large BAM can take a minute or more. One scan runs at a time: a call while one runs is answered
    BUSY (HTTP 409). A scan that finds nothing reads the rest of the chromosome (seconds on a large
    BAM). A running scan can be cancelled, by vx_cancel_coverage_scan or by the panel's pressed button,
    which shows a stop sign while the scan runs: this call then returns at once with cancelled true and
    cancelledBy ("api" or "panel"), the view where it was. A scan that reads nothing for 60 s (a file on
    a disk or share that does not answer) is stopped and answered STALLED (HTTP 504), and a new scan can
    start.

    Args:
        direction: "next" (default) or "prev".
        threshold: Coverage threshold (>= 0; 0: any coverage above 0). Negative uses the
                   spinner's value.
        track: the name of the track to scan (as in vx_get_state); empty for the rule above.

    Returns JSON with moved, scanned (false when no track has coverage to scan), track, trackType,
    targetStart and targetEnd (when moved), scanSeconds (the scan's time), chromosome, viewStart,
    viewEnd, and a note when nothing moved (a note also when the view left the chromosome during the
    scan), and cancelled (true when the scan was cancelled; then cancelledBy, and the note says so).
    """
    kwargs = {"direction": direction}
    if threshold >= 0:
        kwargs["threshold"] = threshold
    if track:
        kwargs["track"] = track
    # the answer comes when the scan ends (a minute or more on a whole chromosome of a large BAM): no client timeout
    r = _vx_post("/command", {"command": "next_coverage_region", "params": kwargs}, timeout=None)
    return json.dumps(_answer(r))


@mcp.tool()
def vx_cancel_coverage_scan() -> str:
    """Cancel the coverage scan in progress (one started by vx_next_coverage_region or by the « » buttons).

    The scan stops at once: its vx_next_coverage_region call returns with cancelled true, the view stays where it
    is, and a new scan can start straight away. Returns cancelled: true with the scan's track and chromosome when
    one was running, else false with "No coverage scan is running".
    """
    return json.dumps(_vx_cmd("cancel_coverage_scan"))


@mcp.tool()
def vx_select_region(
    chromosome: str, start: int, end: int, additive: bool = False
) -> str:
    """Select a genomic region in the viewport (sets cursor selection).

    Args:
        chromosome: Chromosome name (e.g. "chr1", "chrX")
        start: Start position (0-based)
        end: End position (exclusive), must be > start
        additive: If True, add to existing selection instead of replacing it
    """
    if end <= start:
        return json.dumps({"error": "end must be greater than start", "code": "INVALID_PARAMS",
                           "details": f"Got start={start}, end={end}. Provide 0-based coordinates with end > start."})
    return json.dumps(
        _vx_cmd(
            "select_region",
            chromosome=chromosome,
            start=start,
            end=end,
            additive=additive,
        )
    )


# ═══════════════════════════════════════════════════════════════════════
# Phase 2 Tools: Data Queries
# ═══════════════════════════════════════════════════════════════════════


@mcp.tool()
def vx_get_sequence(
    chromosome: str = "",
    start: int = -1,
    end: int = -1,
) -> str:
    """Get the DNA sequence for a genomic region.

    Defaults to the current viewport if no region is specified.
    Maximum 100,000 bases per request.

    Args:
        chromosome: Chromosome name (default: current chromosome)
        start: Start position (default: current view start)
        end: End position (default: current view end)
    """
    params = {}
    if chromosome:
        params["chromosome"] = chromosome
    if start >= 0:
        params["start"] = start
    if end >= 0:
        params["end"] = end
    return json.dumps(_vx_cmd("get_sequence", **params))


@mcp.tool()
def vx_get_genes(
    chromosome: str = "",
    start: int = -1,
    end: int = -1,
) -> str:
    """Get gene annotations in a genomic region.

    Returns gene names, IDs, biotypes, positions, and transcript details.
    Defaults to the current viewport if no region is specified.

    Args:
        chromosome: Chromosome name (default: current chromosome)
        start: Start position (default: current view start)
        end: End position (default: current view end)
    """
    params = {}
    if chromosome:
        params["chromosome"] = chromosome
    if start >= 0:
        params["start"] = start
    if end >= 0:
        params["end"] = end
    return json.dumps(_vx_cmd("get_genes", **params), indent=2)


@mcp.tool()
def vx_search_genes(query: str) -> str:
    """Search for genes by name or ID across all chromosomes.

    Returns up to 100 matching genes with their locations.
    Case-insensitive partial match on gene name and gene ID.

    Args:
        query: Gene name or ID to search for (e.g. "BRCA1", "TP53", "ENS")
    """
    return json.dumps(_vx_cmd("search_genes", query=query), indent=2)


# ═══════════════════════════════════════════════════════════════════════
# Phase 2 Tools: Configuration
# ═══════════════════════════════════════════════════════════════════════


@mcp.tool()
def vx_set_config(
    show_grid: bool | None = None,
    show_labels: bool | None = None,
    dark_mode: bool | None = None,
    track_height: float | None = None,
    interface_scale: float | None = None,
    font_scale: float | None = None,
    active_mode: bool | None = None,
    apply_to_existing: bool | None = None,
) -> str:
    """Update VX display configuration.

    Only provided parameters are changed; others keep their current values.

    Args:
        show_grid: Show genome coordinate grid
        show_labels: Show track labels
        dark_mode: The dark colour scheme of the viewport and of the window's
                   controls (GTK's dark variant; Adwaita's where the desktop theme
                   has none); a capture taken after it shows it
        track_height: The default height, in pixels (at least 10), of every track added
                      from now on in this run of the viewer; since 0.10.0 it changes no
                      existing track unless apply_to_existing is true. Without it a new
                      track takes its type's default from Settings > Track Styles.
        interface_scale: UI scale factor (0.5 to 3.0; a value outside is taken to the nearer end)
        font_scale: Font scale multiplier (0.5 to 4.0; a value outside is taken to the nearer end)
        active_mode: Active mode on or off (hover, select and inspect elements; a
                     vx_click_element needs it on)
        apply_to_existing: With track_height, true also sets that height on every
                           track of the active group (the default is false; a value
                           that is not true or false is refused by name)

    The HTTP command behind this tool refuses a key it does not read, naming it (since 0.10.0); this
    tool sends only the keys it reads.
    """
    params = {}
    if show_grid is not None:
        params["showGrid"] = show_grid
    if show_labels is not None:
        params["showLabels"] = show_labels
    if dark_mode is not None:
        params["darkMode"] = dark_mode
    if track_height is not None:
        params["trackHeight"] = track_height
    if active_mode is not None:
        params["activeModeEnabled"] = active_mode
    if apply_to_existing is not None:
        params["apply_to_existing"] = apply_to_existing
    if interface_scale is not None:
        params["interfaceScale"] = interface_scale
    if font_scale is not None:
        params["fontScale"] = font_scale
    return json.dumps(_vx_cmd("set_config", **params))


@mcp.tool()
def vx_set_magnifier(
    active: bool = True,
    center_x: float | None = None,
    center_y: float | None = None,
    zoom: float | None = None,
    genome_x: int | None = None,
) -> str:
    """Drive the viewport magnifier (Alt+hover loupe) from the API for unattended figure capture.

    Pass active=False to clear the API override and restore Alt+hover gating.

    Args:
        active:    Turn API magnifier on/off (default True).
        center_x:  Magnifier centre X in GL widget pixel coords.
        center_y:  Magnifier centre Y in GL widget pixel coords (default: widget vertical centre).
        zoom:      Magnification factor 1.5-10 (default: current value).
        genome_x:  Genomic position; takes priority over center_x and is mapped via the current viewport.
    """
    params: dict[str, object] = {"active": active}
    if center_x is not None: params["center_x"] = center_x
    if center_y is not None: params["center_y"] = center_y
    if zoom is not None:     params["zoom"]     = zoom
    if genome_x is not None: params["genome_x"] = genome_x
    return json.dumps(_vx_cmd("set_magnifier", **params))


# ═══════════════════════════════════════════════════════════════════════
# Phase 3 Tools: Export
# ═══════════════════════════════════════════════════════════════════════


@mcp.tool()
def vx_export_region(path: str, format: str = "fasta") -> str:
    """Export the current viewport region to a file.

    FASTA writes the reference sequence of the region; GFF writes the genes and features of
    the active group's visible tracks in the region. Since 0.10.0 nothing is written and an
    error is answered when the export has nothing to write: NO_REFERENCE (HTTP 409) with no
    reference genome loaded, NO_ANNOTATION (HTTP 409) for GFF with no gene or feature track in
    the active group; a format other than fasta or gff is INVALID_PARAMS (HTTP 400).

    Args:
        path: Absolute path for the output file
        format: Export format: "fasta" or "gff"
    """
    return json.dumps(_vx_cmd("export_region", path=path, format=format))


@mcp.tool()
def vx_export_svg(
    path: str = "",
    include_ruler: bool | None = None,
    include_grid: bool | None = None,
    include_labels: bool | None = None,
    include_overview: bool | None = None,
    dark_mode: bool | None = None,
    font_family: str = "",
    text_scale: float | None = None,
    track_scale: float | None = None,
) -> str:
    """Export the current viewport as a scalable vector graphic (SVG).

    Produces a publication-quality vector image of all visible tracks.
    Export runs on a background thread; use vx_svg_export_status to poll.
    Only the parameters given are sent (since 0.10.0); every other one takes its
    value from Settings > Capture, as the Export SVG button does.

    Args:
        path: Output file path (absolute). If empty, auto-generates in Snapshots dir.
        include_ruler: Include genomic coordinate ruler at top
        include_grid: Include vertical grid lines
        include_labels: Include track name labels
        include_overview: Include the chromosome overview bar
        dark_mode: Use the dark colour palette for the whole picture (since 0.10.0 the background, ruler
                   and labels too)
        font_family: CSS font-family for text elements
        text_scale: Multiplies the text size (0.1 to 10)
        track_scale: Multiplies every track's height (0.1 to 10)
    """
    params: dict = {}
    if path:
        params["path"] = path
    for key, value in (("include_ruler", include_ruler), ("include_grid", include_grid),
                       ("include_labels", include_labels), ("include_overview", include_overview),
                       ("dark_mode", dark_mode), ("text_scale", text_scale), ("track_scale", track_scale)):
        if value is not None:
            params[key] = value
    if font_family:
        params["font_family"] = font_family
    return json.dumps(_vx_cmd("export_svg", **params))


@mcp.tool()
def vx_svg_export_status() -> str:
    """Check the status of a running SVG export.

    Returns:
        status: "idle", "running", "complete", or "failed"
        message: Human-readable status message
        progress: 0.0 to 1.0
        path: Output file path (when complete)
    """
    return json.dumps(_vx_cmd("svg_export_status"), indent=2)


# ═══════════════════════════════════════════════════════════════════════
# Phase 3 Tools: Loading Status
# ═══════════════════════════════════════════════════════════════════════


@mcp.tool()
def vx_loading_status() -> str:
    """Check if a file is currently being loaded and its progress.

    Returns:
        isLoading: whether a load is in progress
        progress: 0.0 to 1.0
        stage: description of current loading stage
        done: whether loading has completed
        hasError: whether the load that ended last failed (since 0.10.0 also when its track could not be put
                  in the viewer; errorMessage then starts with the step, e.g. "Failed to load track: ...")
        filename: file being loaded
        finalizing: a finished load whose track is not yet in the viewer
        queued: loads waiting behind this one
        cancelled: the load that ended last was cancelled (hasError is true too)

    A client that loads files in order waits for done, not finalizing, and queued 0 before using the track.
    demo: while or after a demo case is opened (vx_load_demo), its job: case, phase (checking, downloading,
    verifying, unpacking, loading, done, failed, cancelled), stage, bytes_done, bytes_total, progress and, once
    fetched, ok, from_cache, resumed, downloaded_bytes, dir, files, error.
    """
    return json.dumps(_vx_cmd("loading_status"), indent=2)


@mcp.tool()
def vx_cancel_loading() -> str:
    """Cancel the file load in progress.

    The load stops at its next progress step, within about a megabyte of what it reads (a VCF,
    BED, bedGraph or Wiggle file, a BAM's header and index included), and the queue goes on with
    the next file; no dialog is shown. Returns cancelled: true when a load was running, else false
    with "No file load to cancel".
    """
    return json.dumps(_vx_cmd("cancel_loading"))


# ═══════════════════════════════════════════════════════════════════════
# Phase 3 Tools: Bookmarks
# ═══════════════════════════════════════════════════════════════════════


@mcp.tool()
def vx_add_bookmark(label: str = "", region: str = "") -> str:
    """Add a bookmark for quick navigation.

    If no region is given, bookmarks the current view once a reference is loaded; before that
    it answers NOT_READY (HTTP 503).

    Args:
        label: Display label for the bookmark (default: the region string)
        region: chromosome:start-end (0-based start, end exclusive, digits alone; the chromosome
                is everything before the last ':'); any other text is refused with INVALID_PARAMS
                (HTTP 400) naming it (default: current view)
    """
    params = {}
    if label:
        params["label"] = label
    if region:
        params["region"] = region
    return json.dumps(_vx_cmd("add_bookmark", **params))


@mcp.tool()
def vx_list_bookmarks() -> str:
    """List all saved bookmarks with their labels and regions."""
    return json.dumps(_vx_cmd("list_bookmarks"), indent=2)


@mcp.tool()
def vx_remove_bookmark(index: int) -> str:
    """Remove a bookmark by its index.

    Args:
        index: 0-based index of the bookmark (from vx_list_bookmarks)
    """
    return json.dumps(_vx_cmd("remove_bookmark", index=index))


@mcp.tool()
def vx_goto_bookmark(index: int) -> str:
    """Navigate to a bookmarked region.

    Goes to the stored region (0-based start, end exclusive), where the bookmark buttons and
    Ctrl+] / Ctrl+[ go; a chromosome named by an alias of the reference is resolved (since 0.10.0).

    Args:
        index: 0-based index of the bookmark (from vx_list_bookmarks)
    """
    return json.dumps(_vx_cmd("goto_bookmark", index=index))


# ═══════════════════════════════════════════════════════════════════════
# Phase 3 Tools: Chromosome List
# ═══════════════════════════════════════════════════════════════════════


@mcp.tool()
def vx_list_chromosomes() -> str:
    """List all chromosomes/contigs in the loaded reference with their lengths.

    Returns count, totalLength, and a list of {name, length} entries.
    """
    return json.dumps(_vx_cmd("list_chromosomes"), indent=2)


# ═══════════════════════════════════════════════════════════════════════
# Phase 3 Tools: Signal Track Options
# ═══════════════════════════════════════════════════════════════════════


@mcp.tool()
def vx_set_signal_options(
    name: str,
    style: str = "",
    scale: str = "",
    y_min: float | None = None,
    y_max: float | None = None,
    auto_scale: bool | None = None,
    smoothing: float | None = None,
    smoothing_method: str = "",
    color_mode: str = "",
    window_function: str = "",
    line_width: float | None = None,
    fill_alpha: float | None = None,
) -> str:
    """Configure display options for a signal track (BigWig, BedGraph, Wiggle).

    Only provided parameters are changed; others keep their current values.

    Args:
        name: Track name (as shown in vx_get_state)
        style: Rendering style: "area", "line", "bars", "heatmap", "step", "points"
        scale: Y-axis scale: "linear", "log2", "log10", "sqrt", "asinh"
        y_min: Manual Y-axis minimum (only when auto_scale=false)
        y_max: Manual Y-axis maximum (only when auto_scale=false)
        auto_scale: Enable/disable auto-scaling of Y-axis
        smoothing: Smoothing window in base pairs (0 = off)
        smoothing_method: Smoothing method: "mean", "median", "max"
        color_mode: Color mapping: "solid", "gradient", "diverging", "heatmap"
        window_function: Aggregation: "mean", "max", "min", "sum", "coverage"
        line_width: Line thickness in pixels (0.5 to 5.0)
        fill_alpha: Fill opacity (0.0 to 1.0)
    """
    params: dict = {"name": name}
    if style:
        params["style"] = style
    if scale:
        params["scale"] = scale
    if y_min is not None:
        params["y_min"] = y_min
    if y_max is not None:
        params["y_max"] = y_max
    if auto_scale is not None:
        params["auto_scale"] = auto_scale
    if smoothing is not None:
        params["smoothing"] = smoothing
    if smoothing_method:
        params["smoothing_method"] = smoothing_method
    if color_mode:
        params["color_mode"] = color_mode
    if window_function:
        params["window_function"] = window_function
    if line_width is not None:
        params["line_width"] = line_width
    if fill_alpha is not None:
        params["fill_alpha"] = fill_alpha
    return json.dumps(_vx_cmd("set_signal_options", **params))


@mcp.tool()
def vx_set_variant_options(
    name: str,
    display_mode: str = "",
    color_mode: str = "",
    filter_pass_only: bool | None = None,
    min_quality: float | None = None,
    min_allele_freq: float | None = None,
    show_labels: bool | None = None,
    show_snps: bool | None = None,
    show_insertions: bool | None = None,
    show_deletions: bool | None = None,
    show_svs: bool | None = None,
    show_other: bool | None = None,
) -> str:
    """Configure display options for a variant track (VCF).

    Only provided parameters are changed; a mode or a switch that is not one of
    those below is refused by name and nothing is changed. The type
    switches and min_allele_freq act on each alternate allele of a record.

    Args:
        name: Track name (as shown in vx_get_state)
        display_mode: Display style: "lollipop", "diamonds", "bars", "density"
                      (density stacks by color_mode)
        color_mode: Color mapping: "type", "quality", "frequency", "filter", "impact",
                    "zygosity"
        filter_pass_only: Only show PASS variants
        min_quality: Hide records with a QUAL below this (records without QUAL are shown)
        min_allele_freq: Hide alleles whose frequency (AF, else AC/AN) is below this
                         (alleles without one are shown)
        show_labels: Show variant IDs as labels
        show_snps: Show SNP variants
        show_insertions: Show insertion variants
        show_deletions: Show deletion variants
        show_svs: Show structural variants and copy-number variants
        show_other: Show multi-base substitutions and complex alleles
    """
    params: dict = {"name": name}
    if display_mode:
        params["display_mode"] = display_mode
    if color_mode:
        params["color_mode"] = color_mode
    if filter_pass_only is not None:
        params["filter_pass_only"] = filter_pass_only
    if min_quality is not None:
        params["min_quality"] = min_quality
    if min_allele_freq is not None:
        params["min_allele_freq"] = min_allele_freq
    if show_labels is not None:
        params["show_labels"] = show_labels
    if show_snps is not None:
        params["show_snps"] = show_snps
    if show_insertions is not None:
        params["show_insertions"] = show_insertions
    if show_deletions is not None:
        params["show_deletions"] = show_deletions
    if show_svs is not None:
        params["show_svs"] = show_svs
    if show_other is not None:
        params["show_other"] = show_other
    return json.dumps(_vx_cmd("set_variant_options", **params))


@mcp.tool()
def vx_set_interaction_options(
    name: str,
    display_mode: str = "",
    color_mode: str = "",
    min_score: float | None = None,
    intra_chr_only: bool | None = None,
    arc_alpha: float | None = None,
    line_width: float | None = None,
) -> str:
    """Configure display options for an interaction track (BEDPE).

    Only provided parameters are changed; others keep their current values.

    Args:
        name: Track name (as shown in vx_get_state)
        display_mode: Display style: "arcs", "heatmap", "links"
        color_mode: Color mapping: "score", "distance", "solid"
        min_score: Minimum interaction score filter
        intra_chr_only: Only show intra-chromosomal interactions; off, a loop to another
                        chromosome is drawn at its anchor, labelled with that chromosome
        arc_alpha: The track's own opacity, 0 to 1, kept on both colour schemes and in
                   the session; without it a loops track is drawn at its scheme's
                   opacity, 0.5 on the light scheme and 0.7 on the dark. The answer
                   gives interaction: opacity (as drawn) and customOpacity
        line_width: Line thickness in pixels
    """
    params: dict = {"name": name}
    if display_mode:
        params["display_mode"] = display_mode
    if color_mode:
        params["color_mode"] = color_mode
    if min_score is not None:
        params["min_score"] = min_score
    if intra_chr_only is not None:
        params["intra_chr_only"] = intra_chr_only
    if arc_alpha is not None:
        params["arc_alpha"] = arc_alpha
    if line_width is not None:
        params["line_width"] = line_width
    return json.dumps(_vx_cmd("set_interaction_options", **params))


@mcp.tool()
def vx_set_alignment_options(
    name: str,
    show_unique_primary: bool | None = None,
    show_multi_primary: bool | None = None,
    show_multi_secondary: bool | None = None,
    show_mate_pairs: bool | None = None,
    show_back_splice: bool | None = None,
    density: str = "",
    read_color_mode: str = "",
    bs_detect_sa: bool | None = None,
    bs_detect_paired_rf: bool | None = None,
    bs_detect_soft_clip: bool | None = None,
    bs_detect_insert_size: bool | None = None,
    bs_soft_clip_min_len: int | None = None,
    bs_insert_size_max: int | None = None,
    show_trans_splice: bool | None = None,
    show_paired_as_fragments: bool | None = None,
    read_sort_mode: str = "",
    segregate_reads_by_class: bool | None = None,
    fragment_stripes: bool | None = None,
    stripe_width: float | None = None,
    stripe_spacing: float | None = None,
    stripe_alpha: float | None = None,
    fragment_gap_alpha: float | None = None,
    show_base_modifications: bool | None = None,
    show_mod_summary_strip: bool | None = None,
    mod_prob_threshold: int | None = None,
    show_polya_tail: bool | None = None,
    show_mod_aggregator: bool | None = None,
    show_polya_aggregator: bool | None = None,
    show_mutation_aggregator: bool | None = None,
    mod_agg_fill_color: list[int] | None = None,
    mod_agg_line_color: list[int] | None = None,
    color_5mc: list[int] | None = None,
    color_5hmc: list[int] | None = None,
    color_6ma: list[int] | None = None,
    color_mod_other: list[int] | None = None,
    polya_agg_fill_color: list[int] | None = None,
    polya_agg_line_color: list[int] | None = None,
    polya_agg_violin_color: list[int] | None = None,
    mut_agg_color_a: list[int] | None = None,
    mut_agg_color_t: list[int] | None = None,
    mut_agg_color_c: list[int] | None = None,
    mut_agg_color_g: list[int] | None = None,
    mut_agg_color_del: list[int] | None = None,
    mut_agg_color_ins: list[int] | None = None,
    mut_agg_total_line_color: list[int] | None = None,
    mut_agg_sub_line_color: list[int] | None = None,
    mut_agg_del_line_color: list[int] | None = None,
    mut_agg_ins_line_color: list[int] | None = None,
    sort_by: str = "",
    sort_order: str = "",
    group_by: str = "",
    packing: str = "",
    mod_extent_unit: str = "",
    multi_mapped_below_mapq: int | None = None,
    filter_min_length: int | None = None,
    filter_max_length: int | None = None,
    filter_min_mapq: int | None = None,
    filter_max_edit_extent: float | None = None,
    filter_min_mod_extent: float | None = None,
    filter_hide_flags: int | None = None,
    reset_layout: bool | None = None,
    filter_indegra: str = "",
    max_reads: int | None = None,
    subsetting: bool | None = None,
    min_mapq: int | None = None,
    show_soft_clips: bool | None = None,
    show_hard_clips: bool | None = None,
    show_quality_scores: bool | None = None,
    show_directionality: bool | None = None,
    show_coverage: bool | None = None,
    coverage_log_scale: bool | None = None,
    coverage_proportion: float | None = None,
    coverage_color_mode: str = "",
    mod_mark_style: str = "",
    reset_colours: bool | None = None,
) -> str:
    """Configure display options for an alignment track (BAM).

    Only provided parameters are changed; others keep their current values.

    Args:
        name: Track name (as shown in vx_get_state)
        show_unique_primary, show_multi_primary, show_multi_secondary: the three class switches, filters of the
            read layout since 0.10.0, applied as the reads load (before the subsample) so the rows close up; a
            value that is not true or false is refused by name. When every read of the view is hidden the track
            says so (vx_get_state: readLayout.hidden_all)
        show_mate_pairs: Draw connecting lines between mate pairs (density 1-2 only)
        show_back_splice: Highlight back-splice / circRNA junction reads in teal with arcs
        density: Density level: "auto", "1", "2", "3", "4", "5"
        read_color_mode: Color reads by: "class", "strand", "insert_size", "solid", "mapq",
                         "indegra" (INDEGRA allocation: a BAM whose header names INDEGRA;
                         by allocation stage whenever a loaded read carries INDEGRA's XS,
                         otherwise by re-allocation; the legend says which)
        bs_detect_sa: Use SA-tag chimeric alignments for back-splice detection
        bs_detect_paired_rf: Use paired-read RF orientation for back-splice detection
        bs_detect_soft_clip: Use large soft-clips for back-splice detection
        bs_detect_insert_size: Use discordant insert size for back-splice detection
        bs_soft_clip_min_len: Minimum soft-clip length (bp) to flag as back-splice
        bs_insert_size_max: Insert size (bp) above which to flag as discordant
        show_trans_splice: Highlight trans-splice reads (SA mapping to different chromosome) in amber
        show_paired_as_fragments: Visualize paired-end reads as unified fragments (same row, gap fill, diagonal stripes)
        read_sort_mode: Visual row ordering: "start_pos" (default, earliest-starting at top), "end_pos" (earliest-ending at top), "length" (shortest at top). Triggers re-pack, no BAM re-fetch.
        segregate_reads_by_class: true is group_by "class" (since 0.10.0): the colour classes under labelled bands,
            unique primary, multi-mapped primary, secondary or supplementary, in fragment mode too
        fragment_stripes: Show diagonal stripes on paired reads (requires show_paired_as_fragments)
        stripe_width: Stripe line width in pixels (0.5-5.0)
        stripe_spacing: Spacing between stripe lines in pixels
        stripe_alpha: Stripe overlay opacity (0.0-1.0)
        fragment_gap_alpha: Fragment inner gap fill opacity (0.0-1.0)
        show_base_modifications: Show base modification marks from MM/ML tags on reads
        show_mod_summary_strip: Show modification summary strip between coverage and reads
        mod_prob_threshold: Minimum modification probability (0-255) to display (default: 128); a change recounts the
            modification summary strip (since 0.10.0)
        show_polya_tail: Show polyA tail blocks at 3' end of reads (from Dorado pt tag)
        show_mod_aggregator: Show modification frequency aggregator strip (stoichiometry per position)
        show_polya_aggregator: Show poly(A) tail length aggregator strip (distribution per 3' end)
        show_mutation_aggregator: Show mutation profile aggregator strip (substitutions, indels per position)
        mod_agg_fill_color: Mod aggregator area fill color [r,g,b] (0-255)
        mod_agg_line_color: Mod aggregator line color [r,g,b]
        color_5mc: 5mC modification color [r,g,b] (affects bars and in-read marks)
        color_5hmc: 5hmC modification color [r,g,b]
        color_6ma: 6mA modification color [r,g,b]
        color_mod_other: Other modification types color [r,g,b]
        polya_agg_fill_color: PolyA aggregator area fill color [r,g,b]
        polya_agg_line_color: PolyA aggregator line color [r,g,b]
        polya_agg_violin_color: PolyA aggregator violin/box plot color [r,g,b]
        mut_agg_color_a: Mutation aggregator substitution-to-A color [r,g,b]
        mut_agg_color_t: Mutation aggregator substitution-to-T color [r,g,b]
        mut_agg_color_c: Mutation aggregator substitution-to-C color [r,g,b]
        mut_agg_color_g: Mutation aggregator substitution-to-G color [r,g,b]
        mut_agg_color_del: Mutation aggregator deletion color [r,g,b]
        mut_agg_color_ins: Mutation aggregator insertion color [r,g,b]
        mut_agg_total_line_color: Mutation total rate line color [r,g,b]
        mut_agg_sub_line_color: Mutation substitution rate line color [r,g,b]
        mut_agg_del_line_color: Mutation deletion rate line color [r,g,b]
        mut_agg_ins_line_color: Mutation insertion rate line color [r,g,b]
        The read layout: filters, then groups, then the sort within each
        group, each group packed into rows of its own under a labelled band; the
        filters apply as the reads load, before the max-reads subsample; a bad
        value fails the call and names its key.
        sort_by: "start" (default, the usual packing), "end", "length" (the read's
                 bases, clips included), "ref_length", "edit_extent" (edits per
                 alignment column), "mod_extent" (calls at or above
                 mod_prob_threshold), "mapq", "strand"
        sort_order: "ascending" (default) or "descending"
        group_by: "none" (default), "type" (primary unique, primary multi-mapped,
                  secondary, supplementary), "strand", "haplotype" (HP tag),
                  "indegra" (re-allocated, not re-allocated, no XR; each in rows of its own),
                  "class" (the colour classes under labelled bands, since 0.10.0)
        packing: "dense" (default) or "one_per_row"
        mod_extent_unit: "per_read" or "per_base"; changing it clears
                         filter_min_mod_extent
        multi_mapped_below_mapq: a primary read without NH is multi-mapped when its
                                 MAPQ is below this (default 1)
        filter_min_length, filter_max_length: read length range in bases (0: off)
        filter_min_mapq: hide reads below this MAPQ (0: off)
        filter_max_edit_extent: 0 to 1 (1: off)
        filter_min_mod_extent: in the unit of mod_extent_unit (0: off)
        filter_hide_flags: SAM flag bits to hide, as samtools view -F (256
                           secondary, 2048 supplementary, 1024 duplicates)
        reset_layout: true restores the default layout before the other keys
        filter_indegra: "all", "hide_reallocated" (reads without XR kept) or
                        "reallocated_only"; applied as the reads load
        The options of the track panel's alignment section. A bad
        value refuses the request and names the key; the reply's `options` holds
        every option of the track as it stands (send the name alone to read them).
        max_reads: reads kept in view when subsampling is on (0: no cap, at most
                   1000000); the view loads again
        subsetting: keep at most max_reads in view, sampled at random
        min_mapq: reads below this mapping quality are not loaded (0 to 255)
        show_soft_clips, show_hard_clips, show_quality_scores, show_directionality,
        show_coverage, coverage_log_scale: the switches of the panel
        coverage_proportion: the coverage strip's share of the track (0: Settings';
                             at most 0.8)
        coverage_color_mode: "solid", "heatmap" or "depth"
        mod_mark_style: "diamond" (the default since 0.10.0) or "classic" (the dots of before)
        reset_colours: reset every colour of the track
    """
    params: dict = {"name": name}
    if show_unique_primary is not None:
        params["show_unique_primary"] = show_unique_primary
    if show_multi_primary is not None:
        params["show_multi_primary"] = show_multi_primary
    if show_multi_secondary is not None:
        params["show_multi_secondary"] = show_multi_secondary
    if show_mate_pairs is not None:
        params["show_mate_pairs"] = show_mate_pairs
    if show_back_splice is not None:
        params["show_back_splice"] = show_back_splice
    if density:
        params["density"] = density
    if read_color_mode:
        params["read_color_mode"] = read_color_mode
    if bs_detect_sa is not None:
        params["bs_detect_sa"] = bs_detect_sa
    if bs_detect_paired_rf is not None:
        params["bs_detect_paired_rf"] = bs_detect_paired_rf
    if bs_detect_soft_clip is not None:
        params["bs_detect_soft_clip"] = bs_detect_soft_clip
    if bs_detect_insert_size is not None:
        params["bs_detect_insert_size"] = bs_detect_insert_size
    if bs_soft_clip_min_len is not None:
        params["bs_soft_clip_min_len"] = bs_soft_clip_min_len
    if bs_insert_size_max is not None:
        params["bs_insert_size_max"] = bs_insert_size_max
    if show_trans_splice is not None:
        params["show_trans_splice"] = show_trans_splice
    if show_paired_as_fragments is not None:
        params["show_paired_as_fragments"] = show_paired_as_fragments
    if read_sort_mode:
        params["read_sort_mode"] = read_sort_mode
    if segregate_reads_by_class is not None:
        params["segregate_reads_by_class"] = segregate_reads_by_class
    for key, value in (("sort_by", sort_by), ("sort_order", sort_order), ("group_by", group_by),
                       ("packing", packing), ("mod_extent_unit", mod_extent_unit),
                       ("filter_indegra", filter_indegra)):
        if value:
            params[key] = value
    for key, value in (("multi_mapped_below_mapq", multi_mapped_below_mapq),
                       ("filter_min_length", filter_min_length), ("filter_max_length", filter_max_length),
                       ("filter_min_mapq", filter_min_mapq), ("filter_max_edit_extent", filter_max_edit_extent),
                       ("filter_min_mod_extent", filter_min_mod_extent), ("filter_hide_flags", filter_hide_flags),
                       ("reset_layout", reset_layout)):
        if value is not None:
            params[key] = value
    if fragment_stripes is not None:
        params["fragment_stripes"] = fragment_stripes
    if stripe_width is not None:
        params["stripe_width"] = stripe_width
    if stripe_spacing is not None:
        params["stripe_spacing"] = stripe_spacing
    if stripe_alpha is not None:
        params["stripe_alpha"] = stripe_alpha
    if fragment_gap_alpha is not None:
        params["fragment_gap_alpha"] = fragment_gap_alpha
    if show_base_modifications is not None:
        params["show_base_modifications"] = show_base_modifications
    if show_mod_summary_strip is not None:
        params["show_mod_summary_strip"] = show_mod_summary_strip
    if mod_prob_threshold is not None:
        params["mod_prob_threshold"] = mod_prob_threshold
    if show_polya_tail is not None:
        params["show_polya_tail"] = show_polya_tail
    if show_mod_aggregator is not None:
        params["show_mod_aggregator"] = show_mod_aggregator
    if show_polya_aggregator is not None:
        params["show_polya_aggregator"] = show_polya_aggregator
    if show_mutation_aggregator is not None:
        params["show_mutation_aggregator"] = show_mutation_aggregator
    # Color overrides (all [r,g,b] arrays)
    for key in [
        "mod_agg_fill_color", "mod_agg_line_color",
        "color_5mc", "color_5hmc", "color_6ma", "color_mod_other",
        "polya_agg_fill_color", "polya_agg_line_color", "polya_agg_violin_color",
        "mut_agg_color_a", "mut_agg_color_t", "mut_agg_color_c", "mut_agg_color_g",
        "mut_agg_color_del", "mut_agg_color_ins",
        "mut_agg_total_line_color", "mut_agg_sub_line_color",
        "mut_agg_del_line_color", "mut_agg_ins_line_color",
    ]:
        val = locals().get(key)
        if val is not None:
            params[key] = val
    for key, value in (("max_reads", max_reads), ("subsetting", subsetting), ("min_mapq", min_mapq),
                       ("show_soft_clips", show_soft_clips), ("show_hard_clips", show_hard_clips),
                       ("show_quality_scores", show_quality_scores), ("show_directionality", show_directionality),
                       ("show_coverage", show_coverage), ("coverage_log_scale", coverage_log_scale),
                       ("coverage_proportion", coverage_proportion), ("reset_colours", reset_colours)):
        if value is not None:
            params[key] = value
    if coverage_color_mode:
        params["coverage_color_mode"] = coverage_color_mode
    if mod_mark_style:
        params["mod_mark_style"] = mod_mark_style
    return json.dumps(_vx_cmd("set_alignment_options", **params))


@mcp.tool()
def vx_add_aggregate_track(source: str, kind: str, options: dict | None = None) -> str:
    """Add a read aggregate track over an alignment track's BAM.

    Args:
        source: The alignment track's name (as shown in vx_get_state)
        kind: "modifications" (per site and modification: stoichiometry, mean
              confidence of the modified calls, coverage; every read in view, not the
              subsample) or "polya" (poly(A) tail lengths per bin)
        options: Any option of vx_set_aggregate_options

    Returns the new track's name.
    """
    params: dict = {"source": source, "kind": kind}
    if options:
        params.update(options)
    return json.dumps(_vx_cmd("add_aggregate_track", **params))


@mcp.tool()
def vx_set_aggregate_options(name: str, options: dict) -> str:
    """Set the options of a read aggregate track.

    Modifications: display bars|line|heat; height stoichiometry|modified|calls|
    confidence; opacity confidence|stoichiometry|none; opacity_floor 0-1;
    colour_mode by_type|single; colour [r,g,b]; code_colours {code: [r,g,b]};
    threshold 0-255 (modified at ML >= threshold); min_coverage; strand both|plus|
    minus. Poly(A): display bars|box|violin; statistic median|mean; anchor
    three_prime|right_end; bin_width (0 auto); y_max (0 auto); min_reads; colour.
    Both: min_mapq; max_span.

    Args:
        name: The aggregate track's name
        options: The options to change, as above
    """
    params: dict = {"name": name}
    params.update(options or {})
    return json.dumps(_vx_cmd("set_aggregate_options", **params))


@mcp.tool()
def vx_aggregate_rows(name: str, chromosome: str, start: int, end: int, bin_width: int = 0) -> str:
    """The counts a read aggregate track gives a region [start, end), counted now with its
    options: modification rows (start, end, base, code, modification, strand,
    calls, modified, stoichiometry, confidence, sites, max_calls) or poly(A) bins (start,
    end, n, mean, median, q1, q3, lower_whisker, upper_whisker, min, max, outliers,
    bandwidth). Counted on the viewer's main thread, bounded by the track's max_span; the answer
    also gives max_span and how it counted (since 0.10.0).

    Args:
        name: The aggregate track's name
        chromosome, start, end: The region, 0-based, end exclusive
        bin_width: The bin width in bases (0: the track's own)
    """
    params: dict = {"name": name, "chromosome": chromosome, "start": start, "end": end}
    if bin_width:
        params["bin_width"] = bin_width
    return json.dumps(_vx_cmd("aggregate_rows", **params))


@mcp.tool()
def vx_add_dti_track(source: str = "", path: str = "") -> str:
    """Add a transcript DTI track (INDEGRA's Direct Transcript Integrity, 0 degraded to
    10 intact) from an INDEGRA alignment track's YD tags (source) or from INDEGRA's
    {sample}_process.txt (path, recognised by its header line).

    Args:
        source: An alignment track's name (as shown in vx_get_state)
        path: INDEGRA's process table, absolute path

    Returns the new track's name.
    """
    params: dict = {}
    if source:
        params["source"] = source
    if path:
        params["path"] = path
    return json.dumps(_vx_cmd("add_dti_track", **params))


@mcp.tool()
def vx_set_dti_options(
    name: str,
    colour_scale: str = "",
    value_min: float | None = None,
    value_max: float | None = None,
    labels: bool | None = None,
) -> str:
    """Set the options of a transcript DTI track.

    Args:
        name: The DTI track's name
        colour_scale: "sequential" or "diverging"
        value_min, value_max: The DTI at the scale's ends (0 to 20; default 0 and 10)
        labels: Show the transcript's name and DTI

    Returns the track's state.
    """
    params: dict = {"name": name}
    if colour_scale:
        params["colour_scale"] = colour_scale
    for key, value in (("value_min", value_min), ("value_max", value_max), ("labels", labels)):
        if value is not None:
            params[key] = value
    return json.dumps(_vx_cmd("set_dti_options", **params))


@mcp.tool()
def vx_dti_lookup(name: str, transcript: str) -> str:
    """A transcript's DTI in a DTI track's table, by the rule the read popup
    uses: the exact ID, else the one ID of its base without a version.

    Args:
        name: The DTI track's name
        transcript: A transcript ID, with or without its version

    Returns match, id and dti.
    """
    return json.dumps(_vx_cmd("dti_lookup", name=name, transcript=transcript))


# ═══════════════════════════════════════════════════════════════════════
# Element clicks, raster export and track scroll (tools since 0.10.0)
# ═══════════════════════════════════════════════════════════════════════


@mcp.tool()
def vx_click_element(x: float, y: float, button: int = 1, ctrl: bool = False) -> str:
    """Click an element of the track area as the mouse would, in widget pixels of the
    OpenGL area (0,0 at its top left corner, at the interface scale in force).

    Active mode must be on (vx_set_config(active_mode=True)); otherwise the answer is
    NOT_READY (HTTP 503). Button 1 is the left click: it selects the element under the
    point (a read, a gene, a variant, a modification mark, a feature) or clears the
    selection on empty space; with ctrl it adds to the selection. Button 3 is the right
    click: on a read not selected or on a modification mark it selects it and opens its
    information popup; anywhere else it opens nothing here (the context menu is not
    opened by the API), and `rightClick` says which the mouse would have done.

    Args:
        x: Horizontal position in the track area, in widget pixels
        y: Vertical position in the track area, in widget pixels
        button: 1 (left, the default) or 3 (right)
        ctrl: With button 1, add to the selection instead of replacing it (the mouse's Ctrl+click,
              Command+click on macOS)

    Returns, in prose: `hit`, whether an element was under the point; `selectedElements`,
    how many are selected now; `popupVisible` and, when the popup is open, `popupText`,
    its text; `selected`, when exactly one element is selected: its trackName, trackType,
    elementIndex and subIndex (a modification call's index, -1 for the element itself);
    with button 3, `rightClick`: "inform" (the popup) or "menu" (the mouse would open the
    context menu).
    """
    params: dict = {"x": x, "y": y, "button": button}
    if ctrl:
        params["ctrl"] = True
    return json.dumps(_vx_cmd("click_element", **params))


@mcp.tool()
def vx_export_image(
    path: str = "",
    format: str = "",
    scale: float | None = None,
    transparent: bool | None = None,
    include_overlays: bool | None = None,
    jpeg_quality: int | None = None,
) -> str:
    """Write the track area to an image file, as the Snapshot button does: the view
    rendered off screen at the scale asked for, with the ruler and every visible track.

    Only the parameters given are sent; every other one takes its value from
    Settings > Capture. Without a path the file goes to the Snapshots directory under
    the configured name pattern. A scale that the GPU cannot render is lowered to the
    largest it can, and the answer says so (`clamped`).

    Args:
        path: Absolute path of the file to write (its extension names the format when
              `format` is empty)
        format: "png", "jpeg" or "tiff"
        scale: The render scale (a positive number; 1.0 is the screen's resolution)
        transparent: PNG and TIFF only: keep the background transparent (straight alpha)
        include_overlays: Draw the selection and hover overlays too
        jpeg_quality: JPEG only, 1 to 100

    Returns, in prose: `path`, the file written; `format`; `width` and `height` in
    pixels; `scale`, the scale used; `clamped`, whether it was lowered; `transparent`,
    whether the file has an alpha channel. A viewer that cannot render answers NOT_READY
    (HTTP 503); a format that is not one of the three is INVALID_PARAMS (HTTP 400).
    """
    params: dict = {}
    if path:
        params["path"] = path
    if format:
        params["format"] = format
    for key, value in (("scale", scale), ("transparent", transparent),
                       ("include_overlays", include_overlays), ("jpeg_quality", jpeg_quality)):
        if value is not None:
            params[key] = value
    return json.dumps(_vx_cmd("export_image", **params))


@mcp.tool()
def vx_set_track_scroll(name: str, offset: float) -> str:
    """Scroll an alignment track's reads vertically, as the track's own scrollbar does.

    Args:
        name: The alignment track's name (as shown in vx_get_state)
        offset: The scroll position in pixels from the top of the read rows (0 is the
                top; a negative value is read as 0; a value past the end scrolls to the
                bottom, since the renderer clamps it at the next frame)

    Returns the confirmation message. A track that is not there answers NOT_FOUND
    (HTTP 404); a track that is not an alignment track answers NOT_SUPPORTED (HTTP 400).
    """
    return json.dumps(_vx_cmd("set_track_scroll", name=name, offset=offset))


# ═══════════════════════════════════════════════════════════════════════
# Analysis Tools
# ═══════════════════════════════════════════════════════════════════════


@mcp.tool()
def vx_list_analyses(tracks: list[str] | None = None) -> str:
    """List available analyses for the currently loaded (or specified) tracks.

    Args:
        tracks: Optional list of track names to check against.
                If omitted, uses all visible tracks.

    Returns JSON with available analyses grouped by category,
    including name, description, and output format.
    """
    params = {}
    if tracks is not None:
        params["tracks"] = tracks
    return json.dumps(_vx_cmd("list_analyses", **params))


@mcp.tool()
def vx_run_analysis(
    analysis: str,
    tracks: list[str] | None = None,
    params: dict | None = None,
    output_path: str = "",
    results_dir: str = "",
) -> str:
    """Run an analysis on loaded tracks.

    Args:
        analysis: Analysis type name, one of the 49 analyses (vx_list_analyses lists
                  those the loaded tracks can take; an unknown name answers
                  UNKNOWN_ANALYSIS, HTTP 400). Common examples: "GCContent", "FeatureCounts",
                  "SignalDifference", "SimplePeakCalling", "MappingQualityDistribution",
                  "CpGDensity", "MotifSearch", "TrackExport".
        tracks: Optional list of track names as input.
                Order matters for A/B analyses (first = A, second = B).
                If omitted, uses all visible tracks.
        params: Optional analysis-specific parameters, e.g.
                {"pseudocount": "1.0", "window_size": "100"}.
                Where the analysis runs: {"scope": "viewport"} (the default
                unless Settings says otherwise) is the window in view,
                {"scope": "chromosome"} the whole of the chromosome in view,
                {"scope": "genome"} every chromosome of the input tracks
                ("group" and "all" are read as "genome"). A reference is a
                transcriptome when at least half of its sequences are named
                as transcripts, or when it holds more than 50 sequences none
                of which reaches 1,000,000 bases (since 0.10.0 a reference
                with a sequence that long is a genome however many it
                holds). On a transcriptome
                reference the sequence in view is a transcript, and
                {"scope": "transcript"} is the same scope by that name
                (scope_applied says "chromosome" for both).
                {"chromosome": "17", "start": "0", "end": "1000000"} names a
                region and takes precedence over the scope (0-based start,
                end exclusive; "chromosome" alone is the whole chromosome).
                Every analysis applies the region. A parameter that does not
                parse or is out of range fails the analysis and names itself;
                vx_analysis_status reports scope_applied, region_applied and
                the parameters the analysis read. What a request does not
                name is the value of Settings, Analysis.
                Parameters of 0.10.0 (each with its default first):
                FeatureCounts, RPKM, TPM and CPM take a BAM and a gene track
                and count reads: {"mode": "union" | "intersection_strict" |
                "intersection_nonempty", "feature": "exon" | "gene",
                "strand": "unstranded" | "forward" | "reverse",
                "min_mapq": "0" (Settings' minimum MAPQ, as for the
                alignment statistics), "primary_only": "true",
                "ignore_duplicates": "false", "count_multimapped": "false",
                "count_qc_failed": "true"};
                RPKM, TPM and CPM also {"library_size": "assigned" | "mapped"
                | a number of reads}. A record that failed QC (0x200) is a
                read; with "count_qc_failed": "false" it is left out and
                counted in the summary's skipped_qc_failed (a record is under
                the first of unmapped, secondary, supplementary, qc_failed,
                low MAPQ, duplicate, multimapped that leaves it out).
                PerExonCoverage and BinStatistics read a BAM's depth with
                Settings' minimum MAPQ unless min_mapq is given, and take
                count_qc_failed ("false" leaves 0x200 records out of the
                depth). BinStatistics: {"bin_size": "10000", "stat": "mean" |
                "median" | "max" | "min" | "sum"}; with a reference loaded a
                chromosome's last bin ends at the reference's length for it,
                else where the input ends (the summary's chromosome_lengths
                says which).
                SimplePeakCalling: {"threshold": "5", "min_width": "100",
                "max_gap": "50", "bg_window": "0"} (the threshold is in
                backgrounds, the median of the values above 0).
                MotifSearch: {"motif": the motif to find, required (no
                default; for example "DRACH"), "strand": "both" | "forward"
                | "reverse"} (IUPAC codes, no regular expression; the default
                strand is both on a genome and forward on a transcriptome; a
                site that both strands match is one row, strand ".").
                GCContent: {"window_size": "1000", "step_size": "500"}; with a
                step below the window each value is written over the step at
                its window's centre, so the bedGraph never overlaps; the
                summary's chromosomes is the number of chromosomes written.
                StrandBias: the fraction is computed in double precision
                (since 0.10.0).
                HeatmapMatrix and ProfilePlotData read a minus-strand feature
                in its own direction (its row runs from its upstream side),
                and read the signal under every bin. IntervalSubtraction and
                TrackExport write a feature without a score as ".".
                TrackExport writes a gene track as eight columns (gene_id,
                gene_name, chrom, start, end, strand, biotype,
                transcript_count), each the gene's model value, whatever the
                annotation's size; through the gene index (a file over 50
                MiB) its summary says "N genes (from index)".
                Without output_path the file is named by its content: .vcf
                for a variant track, .bedgraph for a signal track, .tsv for
                the others.
                A failed analysis is also written to the viewer's log file as an
                ERROR line under the analysis's name (Settings > Paths > Log File
                shows the file).
                Display names since 0.10.0: "Edit Rate" (PerBaseMismatchRate)
                and "Interactions at Features" (InteractionEnrichment); the
                API names are unchanged.
                MismatchRate needs the reference loaded: in each
                bin, the aligned read bases (M, = and X) that differ from the
                reference base under them over the aligned bases compared (an
                N on either side is in neither count); {"bin_size": "1000",
                "primary_only": "true", "ignore_duplicates": "false",
                "min_mapq": "0"}. The Edit Rate (PerBaseMismatchRate) counts
                NM edits and needs no reference.
                InteractionEnrichmentOverExpected: for each
                feature, the anchors on it against those expected if each
                anchor of the chromosome were placed at random, the ratio and
                a Poisson upper-tail p-value; the chromosome's length is the
                loaded reference's, else the largest anchor end (the summary's
                chromosome_lengths says which). No parameter.
                The alignment statistics: {"primary_only": "true",
                "ignore_duplicates": "false", "min_mapq": "0"}; at genome
                scope they also read the records with no reference
                (records_read and skipped_unmapped as samtools flagstat and
                stats count them).
                ChimericReadDensity: {"window_size": "5000", "min_count": "2"};
                on a region the clusters that meet the window, each whole.
                ContactFrequencyVsDistance: {"bins": "50", "log_bins":
                "true"}; on a region the interactions with an anchor in the
                window, each at its whole distance. A missing interaction
                score is left out of every mean and sum ("NA" where none is
                left; interactions_without_score says how many).
                IntervalSubtraction and IntervalUnion on a region give the
                rows genome scope gives for what meets the window.
                SignalCorrelation writes pearson_r and spearman_rho.
                TADBoundaryDetection: {"bin_size": "50000", "window_size":
                "500000", "min_strength": "1", "weight": "score" | "count"}.
                The boundaries found are also put on the interaction track
                the analysis ran on, drawn in its heatmap mode and kept by a
                session (a run at viewport scope gives the track those in
                the window).
                CodingImpact needs the reference loaded
                ({"mitochondrial_code": "vertebrate" |
                "standard", "near_cognate_list": a path to a
                text file of codons, "" the built-in list,
                omitted Settings' list}); an indel is
                left-aligned before it is placed (column
                normalised, POS:REF>ALT as bcftools norm
                writes it), multi-base, complex and indel
                alleles are translated (aa_change in HGVS
                one-letter forms, a deletion or duplication in
                a repeat named at its last place: A5del,
                A5dup, K2_K3delinsNQ, A5Lfs*5), and a start is
                the annotation's (a start_codon line, or no
                cds_start_NF tag in a file without start_codon
                lines), read as Met whatever its codon
                (Ensembl's initial-Met edit, as VEP reads it):
                a change of it is start_lost unless the new
                first codon reads Met (CTG to TTG lost, CTG to
                ATG kept, ATG to ATA kept on chrM), and bases
                put in or taken out at it are read at their
                5'-most placement along the transcript when that
                placement reaches the start codon, so that both
                strands give one row for one change: bases put
                in that reach the start's first base leave the
                three start bases intact and are a 5' UTR row, a
                deletion whose 5'-most placement lies wholly
                before the start is a 5' UTR row, and one that
                still meets the start codon is read there
                (translon_pos and codon_change at that
                placement; the column normalised keeps the left-
                aligned form). The column translon_pos is the
                place
                in the translon, the annotated translated
                region (cds_pos before 0.10.0). The last
                column, near_cognate_start, is yes or no on a
                row whose change alters a start codon, bases put
                in read at their 5'-most placement along the
                transcript whatever the row's (the codon then at
                the start is ATG or in the list:
                the built-in CTG, GTG, TTG, ACG, ATA, ATC,
                ATT, or the file's codons, separated by
                blanks, commas or new lines, '#' a comment, U
                read as T, read at every run), else "."; the
                summary's near_cognate_list names the list. A
                list that cannot be read, holds a token that
                is not a codon or no codon fails the analysis
                by name. VariantAnnotation names the place in
                a translon "translon" (exonic before 0.10.0).
                Since 0.10.0 the translon holds the stop codon a
                GTF gives apart from its CDS lines (stop_codon
                lines), for VariantAnnotation and CodingImpact
                alike (VariantAnnotation called those bases
                3_prime_UTR before).
                VariantAnnotation and VariantIntersection
                left-align indels the same way when the
                reference is loaded (summary normalised,
                moved_by_normalisation, ref_mismatch).
                AlleleFrequencySpectrum counts a frequency in
                the bin whose printed bounds hold it, printed
                with four decimals when the number of bins
                does not divide 100. VariantDensity counts a
                record in the window of its first base (summary
                starts_before_region). TsTvRatio on a region: the
                chromosome's row is the whole chromosome's, the last row the
                region's.
        output_path: Optional explicit output file path.
                     If omitted, auto-generates in the Results directory.
        results_dir: the directory for this run's result files and manifest; the results directory of
                     Settings otherwise.

    Every result file gets a manifest beside it (<result>.manifest.json: the analysis, version, time, each
    input file with size, modification time and SHA-256, the parameters as applied, scope and region, each
    output file with size and SHA-256, the summary, the elapsed seconds); vx_analysis_status's summary names
    it under manifest. An input file above the Settings limit (1024 MB by default) is listed without a hash
    unless params carries hash_inputs: "true" (every input file is checksummed whatever its size).

    Returns status and output path on completion.
    """
    cmd_params: dict[str, Any] = {"type": analysis}
    if tracks is not None:
        cmd_params["tracks"] = tracks
    if params is not None:
        cmd_params["params"] = params
    if output_path:
        cmd_params["output_path"] = output_path
    if results_dir:
        cmd_params["results_dir"] = results_dir
    return json.dumps(_vx_cmd("run_analysis", **cmd_params))


@mcp.tool()
def vx_analysis_status() -> str:
    """Check the progress of a running analysis.

    Returns:
        running: an analysis is in progress (its handler, then the writing of its manifest)
        stage: current stage description
        progress: 0.0 to 1.0
        complete: it has finished: true only with running false, and then success, error,
                  output_path, summary (with the manifest) and parameters are given
        cancelled: whether it was cancelled
        elapsed_seconds: wall-clock time since analysis started
        estimated_remaining_seconds: ETA in seconds (absent if unknown)
    """
    return json.dumps(_vx_cmd("analysis_status"))


@mcp.tool()
def vx_cancel_analysis() -> str:
    """Cancel a running analysis.

    Returns status confirmation or error if no analysis is running.
    """
    return json.dumps(_vx_cmd("cancel_analysis"))


@mcp.tool()
def vx_read_result_rows(path: str, offset: int = 0, limit: int = 100) -> str:
    """Read the rows of a result file an analysis wrote, a page at a time.

    An analysis answers its counts and its output file's path (output_path in vx_analysis_status, and
    the files its summary names); this tool gives that file's rows, such as a gene list. It reads only
    the files the analyses wrote, in this run or in the run that saved a session it reopens (each one's
    output, its manifest and the files its summary names); any other path, a file in the results
    directory included, is refused with NOT_A_RESULT (HTTP 403) before anything of it is read.

    Args:
        path: the result file (output_path from vx_analysis_status); a relative path is read under
              the results directory.
        offset: the first row to give, counted from 0 (default 0).
        limit: how many rows to give, 1 to 1000 (default 100).

    Returns JSON with path; header (a table's column names, a VCF's #CHROM names; [] for a BED or
    bedGraph); rows (each line split on tabs; lines starting with '#', blank lines and a BED or
    bedGraph's track line are not rows); offset; returned; next_offset (the offset of the next page,
    only when more rows follow); bytes (the file's size) and bytes_read; cut_rows (rows longer than
    64 KiB, given cut at that length), when there are any. The file is read from its start to the end
    of the page, never whole.
    """
    # the answer comes when the read ends (a page far into a large file reads every line before it): no client timeout
    r = _vx_post("/command", {"command": "read_result_rows",
                              "params": {"path": path, "offset": offset, "limit": limit}}, timeout=None)
    return json.dumps(_answer(r))


# ═══════════════════════════════════════════════════════════════════════
# Video Recording Tools
# ═══════════════════════════════════════════════════════════════════════


@mcp.tool()
def vx_start_recording(
    format: str = "",
    fps: int | None = None,
    capture_mode: str = "",
    quality: int | None = None,
    output_path: str = "",
) -> str:
    """Start recording the VX viewport to a video file.

    Captures the OpenGL viewport and pipes frames to ffmpeg in real-time.
    Requires ffmpeg to be installed on the system. The parameters are this
    recording's alone: since 0.10.0 nothing here is written to Settings, and a
    parameter not given takes its value from Settings > Capture (as the Record
    button does). A value out of range is refused by name (INVALID_PARAMS).

    Args:
        format: Output format: "mp4" (H.264), "webm" (VP9), or "gif"
        fps: Frames per second for timer capture mode (1 to 240)
        capture_mode: "timer" (fixed FPS) or "render" (every GL frame)
        quality: CRF value: 0=lossless, 18=high, 23=default, 28=low, 51=worst
        output_path: Directory for output file (default: Settings' Snapshots directory)
    """
    params: dict = {}
    if format:
        params["format"] = format
    if fps is not None:
        params["fps"] = fps
    if capture_mode:
        params["capture_mode"] = capture_mode
    if quality is not None:
        params["quality"] = quality
    if output_path:
        params["output_path"] = output_path
    return json.dumps(_vx_cmd("start_recording", **params))


@mcp.tool()
def vx_stop_recording() -> str:
    """Stop an active video recording and finalise the video file.

    Returns:
        status: "stopped"
        frames: the number of frames written
        elapsed: the recording's length as MM:SS
        output_path: the video file written
    With no recording in progress the answer is INVALID_STATE (HTTP 409).
    """
    return json.dumps(_vx_cmd("stop_recording"))


@mcp.tool()
def vx_recording_status() -> str:
    """Check the current status of video recording.

    Returns:
        ffmpeg_available: whether ffmpeg was found on the system PATH
        recording: whether a recording is currently active
        elapsed: elapsed time string (MM:SS) if recording
        frames: number of frames captured so far if recording
    """
    return json.dumps(_vx_cmd("recording_status"))


@mcp.tool()
def vx_load_demo(case: str = "", navigate: bool = True) -> str:
    """Open one of the demo datasets of the VX paper's case studies, each under 1 GB.

    The cases: "1" human K562 RNA-seq on chr19 (718 MB to download), "2" GIAB HG002 variants on
    chr21 (436 MB), "3a" human direct RNA on transcripts (26.1 MB), "3b" yeast aa-tRNA-seq, direct
    RNA, the whole genome (38.9 MB, the quick start), "4" Arabidopsis PacBio HiFi at the Chr1
    centromere (151 MB). VX downloads the case's zip once into its cache directory (from the
    demo-data-v1 release, or from Settings > Paths > Demo Data or VX_DEMO_BASE_URL), checks its
    SHA-256 and every file's, loads the files in order (the reference first) and, with navigate,
    goes to the view of the case's figure. A case already in the cache is not downloaded again; a
    download stopped by vx_cancel_loading resumes at the next call.

    The answer comes at once (the case, its zip, address, sizes, state in the cache, folder, load
    order and view); then poll vx_loading_status until isLoading is false and done is true: it
    reports the download's stage and progress, and its "demo" entry the job (phase, bytes, files,
    error). Refused: an unknown case (400 INVALID_PARAMS, with the list), another case still being
    opened (409 BUSY), an address that is not http or https (409 INVALID_STATE).

    Args:
        case: "1", "2", "3a", "3b" or "4"; empty lists the cases, their sizes and whether each is
            in the cache, and opens nothing
        navigate: go to the view of the case's figure once its files are loaded (default True)
    """
    if not case:
        return json.dumps(_vx_cmd("demo_status"), indent=2)
    return json.dumps(_vx_cmd("load_demo", case=case, navigate=navigate))


# ─── Sessions ───────────────────────────────────────────────────────────

@mcp.tool()
def vx_save_session(path: str) -> str:
    """Write the session to a .vxs file.

    The file holds the view, the display settings, every group's tracks with their settings (the demo's
    tracks by name: reopening the session makes the demo again), the result tracks with their files and the
    bookmarks; a relative path is under the Sessions directory, and .vxs is appended when missing. Returns
    the path written.
    """
    return json.dumps(_vx_cmd("save_session", path=path))


@mcp.tool()
def vx_load_session(path: str) -> str:
    """Restore a .vxs session.

    A session of the demo makes the demo again, with its tracks' settings and order, and the group active
    when the session was saved is active again. Each result file still there is reloaded as its track with
    its manifest's parameters; a missing one is left out. An input file that is not there is skipped, with a
    window or without: no dialog opens. Returns results_reused and results_missing (paths), inputs_missing
    (each input file not found: path, group, and the track it would have made), restore_skipped (each part not
    restored: group, track, reason) and the status line; the files load in the background
    (vx_loading_status, vx_get_state).
    """
    return json.dumps(_vx_cmd("load_session", path=path))


@mcp.tool()
def vx_shutdown() -> str:
    """End the viewer: it answers, then, with a window, saves the window's size, closes it and quits, or, without a
    window, quits. The process has ended 5 s after the answer at the latest (since 0.10.0), even with a dialog left
    open or work still running."""
    return json.dumps(_vx_cmd("shutdown"))


# ─── Entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--sse" in sys.argv:
        mcp.run(transport="sse")
    else:
        mcp.run()
