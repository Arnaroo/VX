#!/usr/bin/env python3
"""
VX Genome Viewer — MCP Server (Phase 2)

Exposes VX's embedded HTTP API as Claude-compatible MCP tools.
Requires the VX application to be running with its API server on port 9876.

Usage:
  python vx_mcp_server.py          # stdio mode (for Claude Code)
  python vx_mcp_server.py --sse    # SSE mode (for web clients)
"""

import base64
import json
import sys
from typing import Any

import httpx
from fastmcp import FastMCP

VX_API_BASE = "http://127.0.0.1:9876"
TIMEOUT = 30.0  # seconds (longer for file loading)

mcp = FastMCP("VX Genome Viewer")


# ─── HTTP helpers ───────────────────────────────────────────────────────


def _vx_get(path: str, **kwargs) -> httpx.Response:
    """GET request to VX API."""
    try:
        r = httpx.get(f"{VX_API_BASE}{path}", timeout=TIMEOUT, **kwargs)
        r.raise_for_status()
        return r
    except httpx.ConnectError:
        raise RuntimeError(
            "[CONNECTION_ERROR] Cannot connect to VX. Is the genome viewer running? "
            "The API server should be listening on 127.0.0.1:9876."
        )
    except httpx.HTTPStatusError as e:
        # Try to extract structured error code from response body
        code = ""
        try:
            body = e.response.json()
            code = body.get("code", "")
        except Exception:
            pass
        code_prefix = f"[{code}] " if code else ""
        raise RuntimeError(f"VX API error: {code_prefix}{e.response.status_code} — {e.response.text}")


def _vx_post(path: str, data: dict) -> httpx.Response:
    """POST request to VX API."""
    try:
        r = httpx.post(f"{VX_API_BASE}{path}", json=data, timeout=TIMEOUT)
        r.raise_for_status()
        return r
    except httpx.ConnectError:
        raise RuntimeError(
            "[CONNECTION_ERROR] Cannot connect to VX. Is the genome viewer running? "
            "The API server should be listening on 127.0.0.1:9876."
        )
    except httpx.HTTPStatusError as e:
        code = ""
        try:
            body = e.response.json()
            code = body.get("code", "")
        except Exception:
            pass
        code_prefix = f"[{code}] " if code else ""
        raise RuntimeError(f"VX API error: {code_prefix}{e.response.status_code} — {e.response.text}")


def _vx_cmd(command: str, **params) -> dict:
    """Send a command to VX via POST /command.

    Returns the parsed JSON response. Error responses include structured fields:
    - error: Human-readable error message
    - code: Machine-readable error code (INVALID_PARAMS, NOT_FOUND, NOT_READY,
            INVALID_STATE, OPERATION_FAILED, UNKNOWN_COMMAND, DEPENDENCY_MISSING,
            TIMEOUT, PARSE_ERROR, UNKNOWN_ENDPOINT, INTERNAL_ERROR)
    - details: Optional additional context or remediation hints
    """
    r = _vx_post("/command", {"command": command, "params": params})
    return r.json()


# ═══════════════════════════════════════════════════════════════════════
# Phase 1 Tools (preserved)
# ═══════════════════════════════════════════════════════════════════════


@mcp.tool()
def vx_ping() -> str:
    """Check if VX genome viewer is running and the API is reachable."""
    r = _vx_get("/ping")
    return r.text


@mcp.tool()
def vx_get_state() -> str:
    """Get the full current state of the VX genome viewer.

    Returns JSON with:
    - chromosome, viewStart, viewEnd, viewLength, zoomLevel
    - activeGroup, tracks (name, type, visible, height)
    - chromosomes (name, length)
    - groups (name, type, isActive, trackCount)
    - config (interfaceScale, fontScale, showGrid, showLabels, darkMode, trackHeight)
    - windowWidth, windowHeight
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
def vx_screenshot(target: str = "full", scale: float = 1.0) -> list[Any]:
    """Capture a screenshot of the VX genome viewer.

    Args:
        target: "full" for the entire window, "viewport" for just the tracks/GL area
        scale: Resolution scale factor (1.0 = screen resolution, 2.0 = 2x, 4.0 = 4x).
               Values > 1.0 use off-screen FBO rendering for publication-quality captures.
               Clamped to 0.5–8.0. Only applies to "viewport" target.

    Returns the image as a base64-encoded PNG suitable for vision models.
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
            {"type": "image", "data": img_b64, "mimeType": "image/png"},
            {"type": "text", "text": f"Screenshot captured ({target}{scale_info}, {len(r.content)} bytes)"},
        ]
    else:
        return [{"type": "text", "text": f"Error: {r.text}"}]


@mcp.tool()
def vx_screenshot_track(track_name: str, scale: float = 1.0) -> list[Any]:
    """Capture a screenshot of a single track from the VX genome viewer.

    Renders just the specified track (with its label area) to a PNG image
    using off-screen FBO rendering. Useful for examining individual tracks
    at high resolution.

    Args:
        track_name: Name of the track to capture (as shown in vx_get_state tracks list)
        scale: Resolution scale factor (1.0 = screen, 2.0 = 2x, 4.0 = 4x). Clamped to 0.5–8.0.

    Returns the image as a base64-encoded PNG suitable for vision models.
    """
    endpoint = f"/screenshot/track?name={track_name}"
    if scale != 1.0:
        endpoint += f"&scale={scale}"
    r = _vx_get(endpoint)

    if r.headers.get("content-type", "").startswith("image/"):
        img_b64 = base64.b64encode(r.content).decode("ascii")
        scale_info = f", {scale}x" if scale != 1.0 else ""
        return [
            {"type": "image", "data": img_b64, "mimeType": "image/png"},
            {"type": "text", "text": f"Track screenshot: {track_name}{scale_info} ({len(r.content)} bytes)"},
        ]
    else:
        return [{"type": "text", "text": f"Error: {r.text}"}]


# ═══════════════════════════════════════════════════════════════════════
# Phase 2 Tools — File Loading
# ═══════════════════════════════════════════════════════════════════════


@mcp.tool()
def vx_load_file(path: str) -> str:
    """Load a genomic file into VX. Auto-detects the file type.

    Supported formats:
    - Reference genomes: .fasta, .fa, .fna
    - Annotations: .gtf, .gff, .gff3
    - Tracks: .bam, .sam, .bed, .bedgraph, .wig, .bigwig
    - Signal: .bigwig, .bw (continuous signal data with indexed random access)
    - Variants: .vcf (SNPs, indels, structural variants)
    - Interactions: .bedpe (paired genomic interactions, Hi-C)
    - Features: .bigbed, .bb (indexed binary BED)

    Loading a reference genome (.fasta) creates a new group.
    Annotations and tracks are added to the active group.

    Args:
        path: Absolute path to the file on the local filesystem
    """
    return json.dumps(_vx_cmd("load_file", path=path))


# ═══════════════════════════════════════════════════════════════════════
# Phase 2 Tools — Track Management
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
# Phase 2 Tools — Group Management
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
# Phase 2 Tools — Navigation & Zoom
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
def vx_next_coverage_region(direction: str = "next", threshold: float = -1.0) -> str:
    """Jump to the next or previous coverage region above a threshold (B6).

    Mirrors the « / » navigation buttons in VX's left control panel.
    Scans the first visible CoverageTrack from the current viewport and
    moves to the start of the next/previous region whose coverage meets
    the threshold.

    Args:
        direction: "next" (default) or "prev".
        threshold: Coverage threshold (>=0). Negative = use the spinner's
                   current value (or 1.0 if no spinner is active).
    Returns JSON with `moved`, `viewStart`, `viewEnd`, `chromosome`.
    """
    kwargs = {"direction": direction}
    if threshold >= 0:
        kwargs["threshold"] = threshold
    return json.dumps(_vx_cmd("next_coverage_region", **kwargs))


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
# Phase 2 Tools — Data Queries
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
# Phase 2 Tools — Configuration
# ═══════════════════════════════════════════════════════════════════════


@mcp.tool()
def vx_set_config(
    show_grid: bool | None = None,
    show_labels: bool | None = None,
    dark_mode: bool | None = None,
    track_height: float | None = None,
    interface_scale: float | None = None,
    font_scale: float | None = None,
) -> str:
    """Update VX display configuration.

    Only provided parameters are changed; others keep their current values.

    Args:
        show_grid: Show genome coordinate grid
        show_labels: Show track labels
        dark_mode: Enable dark mode theme
        track_height: Default track height in pixels
        interface_scale: UI scale factor (0.5-2.0)
        font_scale: Font scale multiplier (0.7-2.0)
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
# Phase 3 Tools — Export
# ═══════════════════════════════════════════════════════════════════════


@mcp.tool()
def vx_export_region(path: str, format: str = "fasta") -> str:
    """Export the current viewport region to a file.

    Args:
        path: Absolute path for the output file
        format: Export format — "fasta" or "gff"
    """
    return json.dumps(_vx_cmd("export_region", path=path, format=format))


@mcp.tool()
def vx_export_svg(
    path: str = "",
    include_ruler: bool = True,
    include_grid: bool = True,
    include_labels: bool = True,
    dark_mode: bool = False,
    font_family: str = "sans-serif",
) -> str:
    """Export the current viewport as a scalable vector graphic (SVG).

    Produces a publication-quality vector image of all visible tracks.
    Export runs on a background thread; use vx_svg_export_status to poll.

    Args:
        path: Output file path (absolute). If empty, auto-generates in Snapshots dir.
        include_ruler: Include genomic coordinate ruler at top
        include_grid: Include vertical grid lines
        include_labels: Include track name labels
        dark_mode: Use dark colour palette
        font_family: CSS font-family for text elements
    """
    params = {}
    if path:
        params["path"] = path
    params["include_ruler"] = include_ruler
    params["include_grid"] = include_grid
    params["include_labels"] = include_labels
    params["dark_mode"] = dark_mode
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
# Phase 3 Tools — Loading Status
# ═══════════════════════════════════════════════════════════════════════


@mcp.tool()
def vx_loading_status() -> str:
    """Check if a file is currently being loaded and its progress.

    Returns:
        isLoading: whether a load is in progress
        progress: 0.0 to 1.0
        stage: description of current loading stage
        done: whether loading has completed
        hasError: whether an error occurred
        filename: file being loaded
    """
    return json.dumps(_vx_cmd("loading_status"), indent=2)


@mcp.tool()
def vx_cancel_loading() -> str:
    """Cancel any in-progress file loading operation."""
    return json.dumps(_vx_cmd("cancel_loading"))


# ═══════════════════════════════════════════════════════════════════════
# Phase 3 Tools — Bookmarks
# ═══════════════════════════════════════════════════════════════════════


@mcp.tool()
def vx_add_bookmark(label: str = "", region: str = "") -> str:
    """Add a bookmark for quick navigation.

    If no region is given, bookmarks the current viewport.

    Args:
        label: Display label for the bookmark (default: the region string)
        region: Genomic region in "chr:start-end" format (default: current view)
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

    Args:
        index: 0-based index of the bookmark (from vx_list_bookmarks)
    """
    return json.dumps(_vx_cmd("goto_bookmark", index=index))


# ═══════════════════════════════════════════════════════════════════════
# Phase 3 Tools — Chromosome List
# ═══════════════════════════════════════════════════════════════════════


@mcp.tool()
def vx_list_chromosomes() -> str:
    """List all chromosomes/contigs in the loaded reference with their lengths.

    Returns count, totalLength, and a list of {name, length} entries.
    """
    return json.dumps(_vx_cmd("list_chromosomes"), indent=2)


# ═══════════════════════════════════════════════════════════════════════
# Phase 3 Tools — Signal Track Options
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
        style: Rendering style — "area", "line", "bars", "heatmap", "step", "points"
        scale: Y-axis scale — "linear", "log2", "log10", "sqrt", "asinh"
        y_min: Manual Y-axis minimum (only when auto_scale=false)
        y_max: Manual Y-axis maximum (only when auto_scale=false)
        auto_scale: Enable/disable auto-scaling of Y-axis
        smoothing: Smoothing window in base pairs (0 = off)
        smoothing_method: Smoothing method — "mean", "median", "max"
        color_mode: Color mapping — "solid", "gradient", "diverging", "heatmap"
        window_function: Aggregation — "mean", "max", "min", "sum", "coverage"
        line_width: Line thickness in pixels (0.5–5.0)
        fill_alpha: Fill opacity (0.0–1.0)
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
) -> str:
    """Configure display options for a variant track (VCF).

    Only provided parameters are changed; others keep their current values.

    Args:
        name: Track name (as shown in vx_get_state)
        display_mode: Display style — "lollipop", "diamonds", "bars", "density"
        color_mode: Color mapping — "type", "quality", "frequency", "filter", "impact"
        filter_pass_only: Only show PASS variants
        min_quality: Minimum QUAL score filter
        min_allele_freq: Minimum allele frequency filter
        show_labels: Show variant IDs as labels
        show_snps: Show SNP variants
        show_insertions: Show insertion variants
        show_deletions: Show deletion variants
        show_svs: Show structural variants
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
        display_mode: Display style — "arcs", "heatmap", "links"
        color_mode: Color mapping — "score", "distance", "solid"
        min_score: Minimum interaction score filter
        intra_chr_only: Only show intra-chromosomal interactions
        arc_alpha: Arc opacity (0.0–1.0)
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
) -> str:
    """Configure display options for an alignment track (BAM).

    Only provided parameters are changed; others keep their current values.

    Args:
        name: Track name (as shown in vx_get_state)
        show_unique_primary: Show uniquely-mapped primary reads
        show_multi_primary: Show multi-mapped primary reads
        show_multi_secondary: Show secondary/supplementary alignments (drawn with dashed outline)
        show_mate_pairs: Draw connecting lines between mate pairs (density 1-2 only)
        show_back_splice: Highlight back-splice / circRNA junction reads in teal with arcs
        density: Density level — "auto", "1", "2", "3", "4", "5"
        read_color_mode: Color reads by — "class", "strand", "insert_size", "solid"
        bs_detect_sa: Use SA-tag chimeric alignments for back-splice detection
        bs_detect_paired_rf: Use paired-read RF orientation for back-splice detection
        bs_detect_soft_clip: Use large soft-clips for back-splice detection
        bs_detect_insert_size: Use discordant insert size for back-splice detection
        bs_soft_clip_min_len: Minimum soft-clip length (bp) to flag as back-splice
        bs_insert_size_max: Insert size (bp) above which to flag as discordant
        show_trans_splice: Highlight trans-splice reads (SA mapping to different chromosome) in amber
        show_paired_as_fragments: Visualize paired-end reads as unified fragments (same row, gap fill, diagonal stripes)
        read_sort_mode: Visual row ordering — "start_pos" (default, earliest-starting at top), "end_pos" (earliest-ending at top), "length" (shortest at top). Triggers re-pack, no BAM re-fetch.
        segregate_reads_by_class: When true, group reads into separate row blocks by class (unique-primary first, then multi-primary, then secondary/supplementary). Combines with read_sort_mode (sort applies within each block). Currently a no-op in paired-fragment mode.
        fragment_stripes: Show diagonal stripes on paired reads (requires show_paired_as_fragments)
        stripe_width: Stripe line width in pixels (0.5-5.0)
        stripe_spacing: Spacing between stripe lines in pixels
        stripe_alpha: Stripe overlay opacity (0.0-1.0)
        fragment_gap_alpha: Fragment inner gap fill opacity (0.0-1.0)
        show_base_modifications: Show base modification marks from MM/ML tags on reads
        show_mod_summary_strip: Show modification summary strip between coverage and reads
        mod_prob_threshold: Minimum modification probability (0-255) to display (default: 128)
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
    return json.dumps(_vx_cmd("set_alignment_options", **params))


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
) -> str:
    """Run an analysis on loaded tracks.

    Args:
        analysis: Analysis type name. Call vx_list_analyses() for all 50+
                  available types. Common examples: "GCContent", "FeatureCounts",
                  "SignalDifference", "SimplePeakCalling", "MappingQualityDistribution",
                  "CpGDensity", "MotifSearch", "TrackExport".
        tracks: Optional list of track names as input.
                Order matters for A/B analyses (first = A, second = B).
                If omitted, uses all visible tracks.
        params: Optional analysis-specific parameters, e.g.
                {"pseudocount": "1.0", "window_size": "100"}.
                Use {"scope": "genome"} to force genome-wide analysis
                instead of the default viewport-scoped behavior.
                Use {"chromosome": "17", "start": "0", "end": "1000000"}
                to restrict to a specific region.
        output_path: Optional explicit output file path.
                     If omitted, auto-generates in the Results directory.

    Returns status and output path on completion.
    """
    cmd_params: dict[str, Any] = {"type": analysis}
    if tracks is not None:
        cmd_params["tracks"] = tracks
    if params is not None:
        cmd_params["params"] = params
    if output_path:
        cmd_params["output_path"] = output_path
    return json.dumps(_vx_cmd("run_analysis", **cmd_params))


@mcp.tool()
def vx_analysis_status() -> str:
    """Check the progress of a running analysis.

    Returns:
        running: whether an analysis is in progress
        stage: current stage description
        progress: 0.0 to 1.0
        complete: whether it has finished
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


# ═══════════════════════════════════════════════════════════════════════
# Video Recording Tools
# ═══════════════════════════════════════════════════════════════════════


@mcp.tool()
def vx_start_recording(
    format: str = "mp4",
    fps: int = 30,
    capture_mode: str = "timer",
    quality: int = 23,
    output_path: str = "",
) -> str:
    """Start recording the VX viewport to a video file.

    Captures the OpenGL viewport and pipes frames to ffmpeg in real-time.
    Requires ffmpeg to be installed on the system.

    Args:
        format: Output format — "mp4" (H.264, default), "webm" (VP9), or "gif"
        fps: Frames per second for timer capture mode (default 30)
        capture_mode: "timer" (fixed FPS, default) or "render" (every GL frame)
        quality: CRF value — 0=lossless, 18=high, 23=default, 28=low, 51=worst
        output_path: Directory for output file (default: configured Snapshots directory)
    """
    params = {
        "format": format,
        "fps": fps,
        "capture_mode": capture_mode,
        "quality": quality,
    }
    if output_path:
        params["output_path"] = output_path
    return json.dumps(_vx_cmd("start_recording", **params))


@mcp.tool()
def vx_stop_recording() -> str:
    """Stop an active video recording and finalise the video file.

    Returns recording statistics including frame count, elapsed time,
    and output file path.
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


# ─── Entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--sse" in sys.argv:
        mcp.run(transport="sse")
    else:
        mcp.run()
