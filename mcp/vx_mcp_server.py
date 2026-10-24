#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Biocodecs Group / Arnaroo Ribologicals
"""
VX: MCP Server

Exposes VX's embedded HTTP API as Claude-compatible MCP tools (80 tools).
Requires the VX application to be running with its API server on port 9876, or at the address the
environment variable VX_API_BASE gives (for example http://127.0.0.1:9911, for a second viewer).

Since 0.10.0 an error answer of the API carries its HTTP status (400 for a request the
client can mend, 403 for a path vx_read_result_rows does not read or, since 0.11.0, a
request sent by a page in a web browser, 404 for a name that is not there, 405 for a
method the API does not take, 409 for a state the request conflicts with, 501 not
implemented, 503 when the viewer cannot serve it now, 504 when the window did not answer
in time or a coverage scan stalled, 500 otherwise) with the
same JSON body as before: `error`, `code` and, where there is one, `details`. Every tool
returns that body as its text, whatever the status; nothing is raised on the status alone.
A request that gets no answer at all (VX is not running at the address in use, the wait ends, the
connection breaks) is answered in that shape by this server, with `error` naming the address and the
command and `code` CONNECTION_ERROR, CLIENT_TIMEOUT or HTTP_ERROR; nothing is raised for it either.
The API sends no CORS header and answers OPTIONS with 405; since 0.11.0 it refuses with 403
FORBIDDEN_ORIGIN, before any command runs, a request a web browser sends for a page (one with
an Origin header, a Host other than 127.0.0.1, localhost or [::1], or a Sec-Fetch-Site other
than none). This server sends none of them.

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


def _what(method: str, path: str, data: dict | None = None) -> str:
    """What a request asks of the viewer, as a message names it: the command of a POST to /command,
    else the method and the path."""
    if data is not None and path == "/command" and isinstance(data.get("command"), str):
        return data["command"]
    return f"{method} {path}"


def _no_answer(exc: Exception, what: str, timeout=None) -> httpx.Response:
    """The answer to a request that the viewer gave none to: made here, never raised. Its body has the
    shape of the API's own error answers (`error`, `code`, `details`) and names the address in use
    (VX_API_BASE) and the command: CONNECTION_ERROR when nothing answers at that address,
    CLIENT_TIMEOUT when the wait ended (the viewer may still carry the request out), HTTP_ERROR for any
    other failure of the exchange."""
    base = VX_API_BASE
    if isinstance(exc, httpx.ConnectError):
        status, code = 503, "CONNECTION_ERROR"
        error = f"Cannot connect to VX at {base} (command: {what}). Is VX running?"
        details = (f"The API server should be listening on {base}: the address VX_API_BASE gives when the "
                   "environment sets it, else http://127.0.0.1:9876. Start VX, or set VX_API_BASE to the "
                   "address its API listens on.")
    elif isinstance(exc, httpx.TimeoutException):
        status, code = 504, "CLIENT_TIMEOUT"
        waited = f" within {timeout:g} s" if isinstance(timeout, (int, float)) else ""
        error = f"VX at {base} did not answer the command {what}{waited}."
        details = "The viewer may still carry the request out: ask for its state (vx_get_state) to see."
    else:
        status, code = 502, "HTTP_ERROR"
        reason = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
        error = f"The request for the command {what} to VX at {base} failed ({reason})."
        details = f"The address in use is {base}: is it the API of a VX viewer?"
    return httpx.Response(status, json={"error": error, "code": code, "details": details})


def _vx_get(path: str, **kwargs) -> httpx.Response:
    """GET request to VX API. The answer is returned whatever its status: since 0.10.0 an
    error answer carries a 4xx or 5xx status with its JSON body, and the caller reads the body.
    A request that gets no answer from the viewer is answered by `_no_answer`, never raised."""
    try:
        return httpx.get(f"{VX_API_BASE}{path}", timeout=TIMEOUT, **kwargs)
    except (httpx.HTTPError, httpx.InvalidURL) as exc:
        return _no_answer(exc, _what("GET", path), TIMEOUT)


def _vx_post(path: str, data: dict, timeout=TIMEOUT) -> httpx.Response:
    """POST request to VX API. The answer is returned whatever its status (see _vx_get); timeout=None
    waits for as long as the viewer takes (a command whose answer comes when its work ends). A request
    that gets no answer from the viewer is answered by `_no_answer`, never raised."""
    try:
        return httpx.post(f"{VX_API_BASE}{path}", json=data, timeout=timeout)
    except (httpx.HTTPError, httpx.InvalidURL) as exc:
        return _no_answer(exc, _what("POST", path, data), timeout)


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
            403 NOT_A_RESULT (a path vx_read_result_rows does not read), FORBIDDEN_ORIGIN (since
            0.11.0: a request sent by a page in a web browser, one with an Origin header, a Host other
            than 127.0.0.1, localhost or [::1], or a Sec-Fetch-Site other than none; this server sends
            none of them);
            404 UNKNOWN_COMMAND, NOT_FOUND, UNKNOWN_ENDPOINT; 405 METHOD_NOT_ALLOWED;
            409 INVALID_STATE, BUSY, NO_REFERENCE, NO_ANNOTATION; 501 NOT_IMPLEMENTED;
            503 NOT_READY, NO_RENDER; 504 STALLED (a coverage scan stopped by its bound), TIMEOUT (the
            window did not answer in time: the request
            may still be carried out, and its answer is not sent; ask for the state to see);
            500 OPERATION_FAILED, IO_ERROR, DEPENDENCY_MISSING, INTERNAL_ERROR and an error
            without a code
            Made by this server when the viewer gave no answer (no HTTP status came from it; each names the
            address in use and the command): CONNECTION_ERROR, CLIENT_TIMEOUT (the wait ended: the request may
            still be carried out), HTTP_ERROR (the exchange failed in another way)
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
    - activeGroup, tracks (name, type, visible, height, selected (whether the track is selected: the Tracks panel's
      tick, which a press on the track's label in the view sets too; since 0.11.0); style (color, label_gap, label_size
      and legend: the keys vx_set_track_options takes); options, the track's own options under the keys its set command takes (coverage,
      signal, variant, interaction; for an interaction track the score colours and opacity as drawn in the scheme
      shown, with custom_colours and custom_opacity), or a gene, feature or sequence track's options under the keys
      of vx_set_gene_options, vx_set_feature_options and vx_set_sequence_options (since 0.11.0: a gene track's give
      isoform_gap, lane_height, lane_gap and its twelve biotype colours, a feature track's row_gap; every
      quantitative type's give its value axis as scale, auto_scale, y_min and y_max); null for a track whose options
      have a key of their own: an alignment track's readLayout,
      indegra, strips and callsMatrix, a read aggregate track's aggregate (with reads_are_rna, the words it names
      modifications in, since 0.11.0) and variants, a DTI track's dti (since 0.11.0);
      an interaction track's interaction: opacity as drawn in the scheme shown, customOpacity true when the user
      set it; a signal track's signal: source "file" or "memory",
      and window: the chromosome in view, the bounds held, zoomLevel (an index into the file's levels, or "raw"),
      stretches, basesPerPixel; null when the track has no such chromosome; a result track's result: analysis,
      analysisName, file, manifest, parameters and note (the analysis's own note from its summary, the words the track
      writes when it holds no record; "" for none; since 0.11.0); a feature track's feature: colour, the one its features are
      drawn in in the scheme shown (the scheme's for features without a colour of their own), customColour
      true when the user set it, fromAnnotation true for a file of features that holds no gene, fileColours
      true when every feature has a colour of its own, a BED's itemRgb, and, since 0.11.0, capListed, capHeld and
      capNoun: how many records the analysis listed, how many the track holds and what they are called, 0, 0 and ""
      for a track that holds all it was given; ORF Prediction's track under its track_cap)
    - axis (since 0.11.0), on each coverage, signal, sequence (the GC curve), Sashimi, overlay and transcript DTI
      track, and coverageAxis on each alignment track (its coverage strip's): the axis the last frame drew, as
      bottom, top, scale, fitted (true: fitted to the values in view; false: the manual range), empty (no value to
      fit), manual_ignored (a manual range that could not be meant, fitted instead) and chromosome, start and end (the
      view it was drawn for, 0-based, end exclusive); null before a frame has drawn the track
    - chromosomes (name, length)
    - groups (name, type, isActive, trackCount; since 0.11.0 also reference, referenceMode, referenceKind,
      referenceWhy and cytobandChromosomes, as below)
    - the active group's reference (since 0.11.0): reference (its file, or "No reference" for a group that has none),
      referenceMode (auto, genome or transcriptome: vx_set_reference_mode), referenceKind (what the reference is read
      as: genome, transcriptome or none), referenceWhy (the reason, such as "42 of 42 sequences are named as
      transcripts") and cytobandChromosomes (how many chromosomes its cytoband table gives bands for; 0 until a table
      is read); bookmarkView ("all" or "group": the left panel's Quick Navigation, vx_list_bookmarks' view) and
      magnifierLocked (whether two taps of Alt keep the magnifier on)
    - config (interfaceScale, fontScale, showGrid, showLabels, darkMode, trackHeight: the height
      vx_set_config(track_height=...) gave tracks added in this run, 0 when none, each type then
      taking its Track Styles height)
    - windowWidth, windowHeight; viewportWidth, viewportHeight (the viewport's size in logical pixels) and
      scaleFactor (since 0.10.0)
    - each interaction track's tadBoundaries once TAD Boundary Detection has run on it: count, and boundaries
      with chromosome, start, end and strength (null when the analysis gave none)
    - each alignment track's readLayout gives hidden_all (every read of the view hidden by the filters) and the three
      class switches; totalMappedReads is the BAM index's count of mapped records; coverageReadTo is the last base
      (1-based) whose depth the coverage strip read whole when the view held more records than the read budget, the
      strip ending there, and null when the window was read whole (since 0.10.0)
    - each alignment track's strips (since 0.11.0): a list of three entries, modifications, polya and mutation, each
      with kind, shown, expanded, height (as laid out: a strip split into lanes is grown for them), own_height and
      own_expanded_height (0: the shared pair), lane_count, drawn (the lanes' plot boxes and axes the last frame drew;
      null before a frame) and view (true once the strip's view is made) and, once it is, counting,
      counted (the window counted as [chromosome, start, end], null before any count), message, and the counts
      held: series, lift_from and lift (modifications), tails (polya), or sites, sites_passing and options
      (mutation: the variant summary's view)
    - each alignment track's callsMatrix (since 0.11.0): the calls matrix the last frame drew (its options, cutoff,
      columns, read_names, cells as a letter a column, bands, notes; see vx_set_alignment_options' display_mode)
    - each read aggregate track's aggregate (since 0.11.0): kind ("modifications", "polya" or "variants"), source (the
      alignment track), bam, reads_are_rna (true: modifications named in RNA words; its source alignment track's
      decision, followed as that changes, since 0.11.0), counting, counted, window
      (chromosome, start, end; null before any count, with a note that says so), binWidth, message, options (as
      vx_set_aggregate_options takes them, as they stand, the height's axis and the lanes among them), drawn (the lanes'
      plot boxes and axes the last frame drew, null before a frame), lift (with lift_from: counted, words, records,
      off_target, absent_calls; null without it) and counts
      (modifications: records, refused, hiddenSites, filteredCalls, testedUnits, testedBins, series and countedUnder,
      the options the counts were made under; poly(A): tails); a variant summary's counts are in its variants: kind,
      options, counting, reference (true when the group's reference was given at the last request), vcf_track, window
      (chromosome, start, end; null before any count) and, once counted, records, sites_listed, sites_passing,
      sites_past_reference and message, with sites_in_view and sites_drawn, the last frame's, and (since 0.11.0)
      q_over (what q is over: "q over the 53 sites listed in chr1:1-2,400"), test (the test in words), sites_untested,
      strand_filtered and strand_unjudged (the sites min_alt_per_strand left out, and the sites listed that it could
      not judge: their reference base under min_alt_per_strand reads on a strand), strand_rule (in words) and control
      (name, bam, counted, records, problem)
    - each Sashimi track's sashimi (since 0.11.0): source, bam, counting, counted, message, window (chromosome,
      start, end, bin), records_read, records_counted, max_depth in view, hide_spanning and spanning_hidden (the
      junctions that span the view, which hide_spanning leaves out of the list, counted) and the junctions in view
      (start 1-based, end, strand, motif, annotated, reads, unique, multi, max_overhang, spans_view)
    - each overlay track's overlay (since 0.11.0): sources (name, color, opacity, present, greatest, covered: the
      share of the view's columns that hold a value), scale, style, line_width, key
    - each interaction track's matrix (since 0.11.0): the Matrix display's value, scale, bin_set, tads, loops, filters
      (Apply filters), bin,
      native, chromosome, bins, pairs, balance_rounds, converged, bins_masked, weight (score or count), balance (the
      Contact Matrix parameters it was balanced with: ignore_diags, min_nnz, mad_max, tolerance, max_rounds) and
      hover (the pair under the pointer at the last hover: chromosome, bin, bin1_start and bin2_start 0-based, count,
      balanced, expected, obs_exp, null for no value, and its words), read for the view (a track out of sight
      answers too; a viewer without OpenGL answers at the track's own matrix_bin)
    - edit: the active group's edit log (operations, position, can_undo, can_redo, the edited sequences with their
      lengths and first changed positions, the tracks the edits changed, the tracks drawn only before the first
      changed position, the paths written) (since 0.11.0)
    - knownFeatures: the Known Features pane's options, shown, active (the tab shown) and tabs, each in short (key,
      id, kind, species, label, title, state, status and each source's outcome) (since 0.11.0)
    - circularView and dotPlot: the open circular view (sequence, length, rings, chords, counting, the switches and
      the layout) and the dot plot's window (whether it holds a plot; its title, word, matches, runs, view and
      frame), each null while closed (since 0.11.0)
    - results_reused, results_missing and results_status after a session load (the status also names what the
      restore did not make and why, since 0.10.0); restore_skipped, each part of the session not restored
      (group, track, reason; a read aggregate track that has no group to go into is named here and in the status
      line alone, since 0.11.0); sessionRestoring (a restore is still applying its tracks' settings: wait for false
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

    Returns the image as a base64-encoded PNG (RGB, no alpha channel) suitable for vision
    models, or the error text: a capture that cannot be rendered (no window yet; no OpenGL
    context for the viewport, as on a viewer without a display) answers NO_RENDER (HTTP 503)
    with the reason in `details`. Since 0.10.0 the image is an MCP image block, which a vision
    model sees (it was a JSON text holding the base64, which no client shows as an image).

    Args:
        target: "full" for the entire window, "viewport" for the track area alone
        scale: Resolution scale factor from 0.25 to 8 (1.0 = screen resolution, 2.0 = 2x);
               a scale outside that range is refused (INVALID_PARAMS, HTTP 400)
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

    Returns the image as a base64-encoded PNG (RGB, no alpha channel) suitable for vision
    models, or the error text: a track that is not among the visible tracks answers NOT_FOUND
    (HTTP 404); a viewer that cannot render (no OpenGL context, as without a display) answers
    NO_RENDER (HTTP 503) with the reason in `details`. Since 0.10.0 the image is an MCP image
    block, which a vision model sees (it was a JSON text holding the base64).

    Args:
        track_name: Name of the track to capture (as shown in vx_get_state tracks list); any
                    name is accepted (it is URL-encoded here, so spaces, '&' and '+' are safe)
        scale: Resolution scale factor from 0.25 to 8 (1.0 = screen, 2.0 = 2x); a scale
               outside that range is refused (INVALID_PARAMS, HTTP 400)
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
      as not found; a file over 50 MiB is read through a gene index saved beside it, format GDX10, an
      older index rebuilt once; since 0.11.0 a GFF3 Parent of several values is read value by value, a
      value that names no gene or transcript of the file, such as a protein's ID, left out and counted
      in one warning line of the log; a gene is its ID on one chromosome, so a gene_id on two chromosomes
      is two genes, and a gene line repeated on one chromosome that overlaps no gene line of its ID there
      begins a gene of its own (Liftoff's copies); files keep the annotation's name and the screens show the
      place (vx_get_genes' displayName); a line's gene is its gene_id, else its geneID (gffread's, as
      FlyBase's GFF3 has it); a transcript line with no gene_id, geneID or Parent belongs to the gene its
      exons make, and without exons to none; a transposon's fragments make a gene of the transposon's ID)
    - Tracks: .bam (alignments), .sam (read as a coverage track: each mapped record counts over its
      aligned bases, an intron's N not counted; since 0.10.0, before as an empty alignment track), .bed,
      .bedgraph, .wig, .bigwig
    - Signal: .bigwig, .bw (continuous signal data with indexed random access)
    - Variants: .vcf (SNPs, indels, structural variants)
    - Interactions: .bedpe (paired genomic interactions, Hi-C); an anchor written end first is read with its two numbers swapped, and one WARN line in the log counts them
    - Not read: .cool, .mcool (HDF5) and .hic (Juicer's format): since 0.11.0 they are refused at once (NOT_SUPPORTED,
      HTTP 400) with the reason; write the contacts as BEDPE (for example with cooler dump --join).
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
        visible: True to show, False to hide (true or false; another value is refused by name). A hidden track
            keeps its row in the track panel, dimmed, and its switch shows it again (since 0.11.0)
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


@mcp.tool()
def vx_set_reference_mode(mode: str, group: str = "") -> str:
    """Set a reference group's mode: how its reference is read, a genome or a transcriptome (since 0.11.0).

    The overview, the analyses' scope words, Motif Search's default strand, ORF Prediction without an annotation and
    the reads' RNA names follow the mode; a session keeps it, and Settings > Paths > Reference mode gives a newly
    loaded reference its mode. The answer gives group, mode, kind (what the reference is read as now: genome or
    transcriptome) and why (the rule's step, such as "4 sequences, 50 or fewer, not named as transcripts", or "set to
    genome"); vx_get_state gives the same for every group (reference, referenceMode, referenceKind, referenceWhy).
    Refused: another word, or no mode (INVALID_PARAMS, HTTP 400); a group that is not there (NOT_FOUND, 404); a group
    without a reference, which has nothing to read (NO_REFERENCE, 409).

    Args:
        mode: "auto" (the default of a group: VX reads the sequences' names and lengths: a transcriptome when at
              least half are named as transcripts, ENST, NM_ and the like in any letter case, one sequence alone
              too; a genome when a sequence is 1,000,000 bases or longer or there are 50 or fewer; of more than 50
              shorter ones, a genome when at least half are named as contigs, scaffolds or chromosomes, else a
              transcriptome), "genome" or "transcriptome" (case is not read)
        group: The group's name (as vx_get_state lists the groups); empty for the active group
    """
    params: dict = {"mode": mode}
    if group:
        params["group"] = group
    return json.dumps(_vx_cmd("set_reference_mode", **params))


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

    Returns JSON with moved, scanned (false when no track has coverage to scan), track, trackType,
    targetStart and targetEnd (when moved), scanSeconds (the scan's time), chromosome, viewStart,
    viewEnd, and a note when nothing moved (a note also when the view left the chromosome during the
    scan), and cancelled (true when the scan was cancelled; then cancelledBy, and the note says so).

    Args:
        direction: "next" (default) or "prev".
        threshold: Coverage threshold (>= 0; 0: any coverage above 0). Negative uses the
                   spinner's value.
        track: the name of the track to scan (as in vx_get_state); empty for the rule above.
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
    Each gene's geneName is the annotation's own name and displayName the name VX shows it by (since 0.11.0):
    "ATCG00150 (ChrC)" for an ID on several chromosomes, "ATMG01360 (Chr2:3,591,778)" for one of the copies of an
    ID on one chromosome (Liftoff's); chromosome, start and end tell them apart too.

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
    An ID on two chromosomes, or twice on one (Liftoff's copies), answers once for each gene, with geneName and
    displayName as vx_get_genes gives them (since 0.11.0).

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

    The HTTP command behind this tool refuses a key it does not read, naming it (since 0.10.0); this
    tool sends only the keys it reads.

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

    Produces a vector image of all visible tracks; since 0.11.0 the gene, signal, interaction and transcript DTI
    tracks are drawn as the screen draws them (from its scroll), and the ruler and grid stand over the bases of the
    tracks.
    Export runs on a background thread; use vx_svg_export_status to poll.
    Only the parameters given are sent (since 0.10.0); every other one takes its
    value from Settings > Capture, as the Export SVG button does.

    Args:
        path: Output file path (absolute). If empty, auto-generates in Snapshots dir.
        include_ruler: Include genomic coordinate ruler at top
        include_grid: Include vertical grid lines
        include_labels: Include the label column (track names and legends); the names inside a track follow that
                        track's Show labels
        include_overview: Include the chromosome overview bar
        dark_mode: Use the dark colour palette for the whole picture (since 0.10.0 the background, ruler
                   and labels too)
        font_family: CSS font-family for text elements
        text_scale: Multiplies the text size (0.1 to 10)
        track_scale: Multiplies every track's height and, as the toolbar's Scale does, the sizes and text inside the
                     tracks (since 0.11.0; the DTI track's text follows it too) (0.1 to 10)
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

    Returns JSON with:
    - status: "idle", "running", "complete", or "failed"
    - message: Human-readable status message
    - progress: 0.0 to 1.0
    - path: Output file path (when complete)
    """
    return json.dumps(_vx_cmd("svg_export_status"), indent=2)


# ═══════════════════════════════════════════════════════════════════════
# Phase 3 Tools: Loading Status
# ═══════════════════════════════════════════════════════════════════════


@mcp.tool()
def vx_loading_status() -> str:
    """Check if a file is currently being loaded and its progress.

    Returns JSON with:
    - isLoading: whether a load is in progress
    - progress: 0.0 to 1.0
    - stage: description of current loading stage
    - done: whether loading has completed
    - hasError: whether the load that ended last failed (since 0.10.0 also when its track could not be put
      in the viewer; errorMessage then starts with the step, e.g. "Failed to load track: ...")
    - filename: file being loaded
    - finalizing: a finished load whose track is not yet in the viewer
    - queued: loads waiting behind this one
    - cancelled: the load that ended last was cancelled (hasError is true too)

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
def vx_add_bookmark(label: str = "", region: str = "", group: str | None = None) -> str:
    """Add a bookmark for quick navigation.

    If no region is given, bookmarks the current view once a reference is loaded; before that
    it answers NOT_READY (HTTP 503).

    Since 0.11.0 a bookmark belongs to a reference group ("" for every group): pressing a bookmark of another
    group switches to that group first.

    The answer names the bookmark's group (group).

    Args:
        label: Display label for the bookmark (default: the region string)
        region: chromosome:start-end (0-based start, end exclusive, digits alone; the chromosome
                is everything before the last ':'); any other text is refused with INVALID_PARAMS
                (HTTP 400) naming it (default: current view)
        group: The bookmark's reference group (as vx_get_state lists the groups); "" keeps it for every group;
               left out, the group whose reference holds the region's chromosome (each group's own aliases), the
               active group first, else every group. A name that is no open group is refused (NOT_FOUND, HTTP
               404) before anything changes.
    """
    params = {}
    if label:
        params["label"] = label
    if region:
        params["region"] = region
    if group is not None:
        params["group"] = group
    return json.dumps(_vx_cmd("add_bookmark", **params))


@mcp.tool()
def vx_list_bookmarks(view: str = "") -> str:
    """List the saved bookmarks with their index (the one vx_goto_bookmark and vx_remove_bookmark take), label,
    region and, since 0.11.0, group ("" for a bookmark kept for every group).

    The answer gives count, bookmarks, activeGroup and view (the panel's, "all" or "group"; vx_get_state gives it
    as bookmarkView). An index is the bookmark's place among every bookmark, whatever the view lists.

    Args:
        view: "group" sets the left panel's Quick Navigation to This group and lists what it shows (the active
              group's bookmarks and those kept for every group); "all" sets it to All and lists every bookmark;
              empty lists every bookmark and changes nothing. Another word is refused (INVALID_PARAMS, HTTP 400)
              before anything changes.
    """
    params = {}
    if view:
        params["view"] = view
    return json.dumps(_vx_cmd("list_bookmarks", **params), indent=2)


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
    A bookmark of another reference group switches to that group first (since 0.11.0): the answer names the
    group gone to (group) and whether it was a switch (switched).

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
def vx_set_coverage_options(
    name: str,
    style: str = "",
    scale: str = "",
    color_mode: str = "",
    fill_color: list[int] | None = None,
    line_color: list[int] | None = None,
    line_width: float | None = None,
    fill_alpha: float | None = None,
    show_fill: bool | None = None,
    auto_scale: bool | None = None,
    y_min: float | None = None,
    y_max: float | None = None,
) -> str:
    """Configure display options for a coverage track (the track panel's coverage section).

    Only provided parameters are changed. Every value is checked before anything changes: a
    word not among those below, a switch that is not true or false, a number out of range,
    a colour that is not [r, g, b] with each 0 to 255, or a key the command does not read is
    refused by name, and nothing is changed (since 0.11.0).

    The answer gives options, the track's coverage options as set, under the same keys (scale, auto_scale, y_min,
    y_max among them); vx_get_state gives the axis the last frame drew as the track's axis.

    Args:
        name: Track name (as shown in vx_get_state)
        style: "area", "line", "bars", "heatmap"
        scale: The value axis's transform (since 0.11.0): "linear", "log2", "log10", "sqrt" or "asinh" ("log", the
               word of 0.10.0's Log switch, is read as log10)
        color_mode: "solid", "heatmap" (the heat ramp by depth; the Heatmap style always uses it)
        fill_color: [r, g, b] of the Area fill and the bars
        line_color: [r, g, b] of the Area outline and the Line style
        line_width: 0.5 to 10 pixels (the bars' width in the Bars style)
        fill_alpha: 0 to 1
        show_fill: The Area style's fill (and the Bars style's bars)
        auto_scale: true (the default since 0.11.0): the axis is fitted to the depths in view, the largest at 95
                    percent of the height and 0 kept; false: y_min to y_max
        y_min: The bottom of the axis while auto_scale is false, -1e9 to 1e9
        y_max: The top of the axis while auto_scale is false, -1e9 to 1e9; with auto_scale false the top must be
               above the bottom, or the request is refused by name (a range given while auto_scale is true is
               kept for when it is switched off)
    """
    params: dict = {"name": name}
    if style:
        params["style"] = style
    if scale:
        params["scale"] = scale
    if color_mode:
        params["color_mode"] = color_mode
    if fill_color is not None:
        params["fill_color"] = fill_color
    if line_color is not None:
        params["line_color"] = line_color
    if line_width is not None:
        params["line_width"] = line_width
    if fill_alpha is not None:
        params["fill_alpha"] = fill_alpha
    if show_fill is not None:
        params["show_fill"] = show_fill
    for key, value in (("auto_scale", auto_scale), ("y_min", y_min), ("y_max", y_max)):
        if value is not None:
            params[key] = value
    return json.dumps(_vx_cmd("set_coverage_options", **params))


@mcp.tool()
def vx_set_track_options(
    name: str,
    color: list[int] | None = None,
    label_gap: float | None = None,
    label_size: float | None = None,
    legend: bool | None = None,
) -> str:
    """Set the controls every track has in the track panel: its label colour, label gap,
    label size and legend.

    Only provided parameters are changed; a value out of range or a key the command does
    not read is refused by name and nothing is changed (since 0.11.0).

    The answer gives style, the track's common controls as set.

    Args:
        name: Track name (as shown in vx_get_state)
        color: [r, g, b] of the track's label (its accent bar and name); also a gene track's
               genes in Uniform colouring and an alignment track's reads in Solid colouring
        label_gap: The gap between the label's lines and between its legend's rows, 0 to 30 px
        label_size: The label's text size, 0 to 18 pt (0: automatic)
        legend: The legend in the track's label; when the track is too short for its first
                row, the label says "Legend hidden: raise height"
    """
    params: dict = {"name": name}
    if color is not None:
        params["color"] = color
    if label_gap is not None:
        params["label_gap"] = label_gap
    if label_size is not None:
        params["label_size"] = label_size
    if legend is not None:
        params["legend"] = legend
    return json.dumps(_vx_cmd("set_track_options", **params))


@mcp.tool()
def vx_set_gene_options(
    name: str,
    show_labels: bool | None = None,
    color_mode: str = "",
    body_height: float | None = None,
    isoform_row_height: float | None = None,
    isoform_gap: float | None = None,
    lane_height: float | None = None,
    lane_gap: float | None = None,
    intron_width: float | None = None,
    row_spacing: float | None = None,
    opacity: float | None = None,
    feature_label_size: float | None = None,
    gene_name_size: float | None = None,
    per_track_colours: bool | None = None,
    biotype_colours: dict | None = None,
    lod_density_ppb: float | None = None,
    lod_boundary_ppb: float | None = None,
    lod_feature_ppb: float | None = None,
) -> str:
    """Set a gene track's options, as its section of the track panel does (since 0.11.0).

    Only provided parameters are changed. Every value is checked before anything changes: a word not among
    those below, a switch that is not true or false, a number out of range, a colour that is not [r, g, b] with
    each 0 to 255, or a key the command does not read is refused by name (INVALID_PARAMS, HTTP 400), and
    nothing is changed. An open track panel row shows the new values. A track that is not a gene track is
    refused (NOT_SUPPORTED).

    The answer gives options, the track's options as set (vx_get_state gives them too, under the same keys).

    Args:
        name: Track name (as shown in vx_get_state)
        show_labels: Every text the track draws on its body: the genes' and transcripts' names, "+N more
                     isoforms", the detailed view's translon, UTR, intron and exon-length labels and the exons'
                     numbered badges, on screen and in the SVG export (the density level's scale stays)
        color_mode: "biotype" or "uniform" (Uniform colouring uses the track's colour, vx_set_track_options'
                    color)
        body_height: A gene's body, 6 to 120 pixels (a base value that the levels of detail scale)
        isoform_row_height: Each isoform's row in the detailed view, 0 to 120 pixels (0: body_height)
        isoform_gap: The space between isoforms, -1 to 40 pixels (-1: automatic, 1.5 x row_spacing; 10 for a
                     new track since 0.11.0)
        lane_height: Each of the two lanes of a transcript in its own coordinates (a transcriptome's annotation,
                     or a transcript with a retained intron: its structure above, its exons below), 0 to 60
                     pixels (0: the two lanes share the isoform row, 0.3 of it each; 14 for a new track since
                     0.11.0)
        lane_gap: The space between those two lanes, -1 to 60 pixels (-1: automatic, 4/3 of a lane; 18 for a new
                  track since 0.11.0)
        intron_width: The intron line, 0.5 to 8 pixels
        row_spacing: The space between rows of genes, 0 to 20 pixels (a base value)
        opacity: 0.1 to 1
        feature_label_size: The detailed view's labels, 0 to 18 points (0: automatic)
        gene_name_size: The genes' names, 0 to 18 points (0: automatic)
        per_track_colours: true gives the track its own biotype colours instead of Settings'
        biotype_colours: Any of color_protein_coding, color_lncrna, color_circrna, color_trna, color_rrna,
                         color_mirna, color_snrna, color_snorna, color_pseudogene, color_ig_tr, color_misc_rna,
                         color_default, each [r, g, b]
        lod_density_ppb: The density level of detail's threshold, 0 to 10 pixels a base (0: Settings')
        lod_boundary_ppb: The boundary level of detail's threshold, 0 to 10 pixels a base (0: Settings')
        lod_feature_ppb: The feature level of detail's threshold, 0 to 10 pixels a base (0: Settings')
    """
    params: dict = {"name": name}
    if color_mode:
        params["color_mode"] = color_mode
    for key, value in (("show_labels", show_labels), ("body_height", body_height),
                       ("isoform_row_height", isoform_row_height), ("isoform_gap", isoform_gap),
                       ("lane_height", lane_height), ("lane_gap", lane_gap), ("intron_width", intron_width),
                       ("row_spacing", row_spacing), ("opacity", opacity),
                       ("feature_label_size", feature_label_size), ("gene_name_size", gene_name_size),
                       ("per_track_colours", per_track_colours), ("lod_density_ppb", lod_density_ppb),
                       ("lod_boundary_ppb", lod_boundary_ppb), ("lod_feature_ppb", lod_feature_ppb)):
        if value is not None:
            params[key] = value
    if biotype_colours:
        params.update(biotype_colours)
    return json.dumps(_vx_cmd("set_gene_options", **params))


@mcp.tool()
def vx_set_feature_options(
    name: str,
    show_labels: bool | None = None,
    box_height: float | None = None,
    row_gap: float | None = None,
    corner_radius: float | None = None,
    opacity: float | None = None,
    feature_colour: list[int] | None = None,
    custom_colour: bool | None = None,
) -> str:
    """Set a feature track's options (BED, BigBed, an annotation without genes, an analysis's features), as its
    section of the track panel does (since 0.11.0).

    Only provided parameters are changed. Every value is checked before anything changes: a switch that is not
    true or false, a number out of range, a colour that is not [r, g, b] with each 0 to 255, or a key the command
    does not read is refused by name (INVALID_PARAMS, HTTP 400), and nothing is changed. A junction track's Sashimi
    keys (display, min_count, arc_scale, show_counts) are vx_set_sashimi_options', and are refused here with that
    tool named. A track that is not a feature track is refused (NOT_SUPPORTED).

    The boxes, the gap and the corners follow the toolbar's Scale and the SVG export's track scale. The answer
    gives options, the track's options as set (vx_get_state gives them too, under the same keys).

    Args:
        name: Track name (as shown in vx_get_state)
        show_labels: The features' names
        box_height: The boxes' height, 4 to 60 pixels (18 for a new track since 0.11.0; 20 in 0.10.0)
        row_gap: The space between rows of overlapping features, 0 to 40 pixels (6 for a new track since 0.11.0)
        corner_radius: 0 to 20 pixels (held to half the box's shorter side)
        opacity: 0.1 to 1
        feature_colour: [r, g, b], the colour of every feature, kept on both colour schemes (it makes the
                        colour the user's: custom_colour true)
        custom_colour: false gives the file's colours (a BED's itemRgb) or the scheme's back
    """
    params: dict = {"name": name}
    for key, value in (("show_labels", show_labels), ("box_height", box_height), ("row_gap", row_gap),
                       ("corner_radius", corner_radius), ("opacity", opacity),
                       ("feature_colour", feature_colour), ("custom_colour", custom_colour)):
        if value is not None:
            params[key] = value
    return json.dumps(_vx_cmd("set_feature_options", **params))


@mcp.tool()
def vx_set_sequence_options(
    name: str,
    show_bases: bool | None = None,
    show_gc: bool | None = None,
    color_scheme: str = "",
    scale: str = "",
    auto_scale: bool | None = None,
    y_min: float | None = None,
    y_max: float | None = None,
) -> str:
    """Set a sequence track's options, as its section of the track panel does: its bases, its GC curve and the
    curve's value axis (since 0.11.0).

    Only provided parameters are changed. Every value is checked before anything changes: a switch that is not
    true or false, a colour scheme that is not one of those below, a scale word that is not one of the five, a
    number that is not finite or lies outside -1e9 to 1e9, a range whose top is not above its bottom while auto_scale
    is false, or a key the command does not read is refused by name (INVALID_PARAMS, HTTP 400), and nothing is
    changed. A track that is not a sequence track is refused (NOT_SUPPORTED).

    The answer gives options, the track's options as set, under the same keys (show_bases, show_gc,
    color_scheme, scale, auto_scale, y_min, y_max); vx_get_state gives them too, and the axis the last frame drew
    as the track's axis.

    Args:
        name: Track name (as shown in vx_get_state)
        show_bases: The bases drawn as letters or blocks at high zoom
        show_gc: The GC curve
        color_scheme: "default" (Settings > Track Styles > Sequence Track's colours: A green, T red, C blue,
                      G orange, N grey), "ncbi", "sanger" or "colorblind"
        scale: The GC curve's scale: "linear", "log2", "log10", "sqrt" or "asinh"
        auto_scale: true (the default for a new track): the axis is fitted to the GC percentages in view (the
                    curve's own span, in percent: 0 is not kept); false: y_min to y_max
        y_min: The bottom of the axis in percent while auto_scale is false (a range given alone leaves
               auto_scale as it is and is kept for when it is switched off)
        y_max: The top of the axis in percent while auto_scale is false
    """
    params: dict = {"name": name}
    for key, value in (("color_scheme", color_scheme), ("scale", scale)):
        if value:
            params[key] = value
    for key, value in (("show_bases", show_bases), ("show_gc", show_gc), ("auto_scale", auto_scale),
                       ("y_min", y_min), ("y_max", y_max)):
        if value is not None:
            params[key] = value
    return json.dumps(_vx_cmd("set_sequence_options", **params))


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
    show_axis: bool | None = None,
    fill_color: list[int] | None = None,
    line_color: list[int] | None = None,
    negative_color: list[int] | None = None,
    show_negative: bool | None = None,
) -> str:
    """Configure display options for a signal track (BigWig, BedGraph, Wiggle).

    Only provided parameters are changed. Every value is checked before anything changes: a
    word not among those below, a switch that is not true or false, a number out of range, a
    colour that is not [r, g, b] with each 0 to 255, or a key the command does not read is
    refused by name, and nothing is changed (since 0.11.0; before, an unknown word read as the
    first one and a switch that was not true read as false). An open track panel row shows the
    new values.

    Args:
        name: Track name (as shown in vx_get_state)
        style: Rendering style: "area", "line", "bars", "heatmap", "step", "points"
        scale: Y-axis scale: "linear", "log2", "log10", "sqrt", "asinh"
        y_min: Manual Y-axis minimum (drawn while auto_scale is false), -1e9 to 1e9
        y_max: Manual Y-axis maximum (drawn while auto_scale is false), -1e9 to 1e9; with auto_scale false the top
               must be above the bottom, or the request is refused by name (a track took such a range until 0.11.0
               and drew the view's fit in silence)
        auto_scale: true (the default since 0.11.0): the axis is fitted to the values in view as the track draws them
                    (each column's value after the window function and smoothing), the largest at 95 percent of
                    its side of the plot and 0 kept, a CNV Segmentation bins track leaving its -20 (a bin without
                    reads) out of the fit; false: y_min to y_max
        smoothing: Smoothing window in base pairs, 0 (off) to 1,000,000
        smoothing_method: Smoothing method: "mean", "median", "max"
        color_mode: Color mapping: "solid", "gradient", "diverging", "heatmap"
        window_function: Aggregation: "mean", "max", "min", "sum", "coverage"
        line_width: Line thickness in pixels, 0.5 to 10 (the Points style's dot radius)
        fill_alpha: Fill opacity, 0 to 1
        show_axis: The value axis
        fill_color: [r, g, b] of the fill (Area, Bars, Step, Points in Solid colouring)
        line_color: [r, g, b] of the line (Area, Line, Step)
        negative_color: [r, g, b] of the bars below 0 (Bars)
        show_negative: Draw values below 0 below the zero line (true, the default); false draws them at 0 (since
                       0.11.0)
    """
    params: dict = {"name": name}
    for key, value in (("style", style), ("scale", scale), ("smoothing_method", smoothing_method),
                       ("color_mode", color_mode), ("window_function", window_function)):
        if value:
            params[key] = value
    for key, value in (("y_min", y_min), ("y_max", y_max), ("auto_scale", auto_scale), ("smoothing", smoothing),
                       ("line_width", line_width), ("fill_alpha", fill_alpha), ("show_axis", show_axis),
                       ("fill_color", fill_color), ("line_color", line_color), ("negative_color", negative_color),
                       ("show_negative", show_negative)):
        if value is not None:
            params[key] = value
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
    stem_height: float | None = None,
    marker_size: float | None = None,
    opacity: float | None = None,
    color_snp: list[int] | None = None,
    color_insertion: list[int] | None = None,
    color_deletion: list[int] | None = None,
    color_mnp: list[int] | None = None,
    color_sv: list[int] | None = None,
    color_cnv: list[int] | None = None,
    color_complex: list[int] | None = None,
) -> str:
    """Configure display options for a variant track (VCF).

    Only provided parameters are changed; a mode or a switch that is not one of
    those below, a number out of range, a colour that is not [r, g, b] with each 0
    to 255, or a key the command does not read (since 0.11.0) is refused by name and
    nothing is changed. The type switches and min_allele_freq act on each alternate
    allele of a record. An open track panel row shows the new values.

    Args:
        name: Track name (as shown in vx_get_state)
        display_mode: Display style: "lollipop", "diamonds", "bars", "density"
                      (density stacks by color_mode)
        color_mode: Color mapping: "type", "quality", "frequency", "filter", "impact",
                    "zygosity"
        filter_pass_only: Only show PASS variants
        min_quality: Hide records with a QUAL below this, 0 or more (records without QUAL are shown)
        min_allele_freq: Hide alleles whose frequency (AF, else AC/AN) is below this, 0 to 1
                         (alleles without one are shown)
        show_labels: Show variant IDs as labels
        show_snps: Show SNP variants
        show_insertions: Show insertion variants
        show_deletions: Show deletion variants
        show_svs: Show structural variants and copy-number variants
        show_other: Show multi-base substitutions and complex alleles
        stem_height: The lollipop's stem as a fraction of the track, 0.1 to 1
        marker_size: The marker's radius in pixels, 2 to 20 (the lollipop circle; the diamond's half width)
        opacity: 0.1 to 1
        color_snp: [r, g, b] of the SNP type (Color by type; and for records without an impact or a genotype under
                 impact and zygosity)
        color_insertion: [r, g, b] of the insertion type (Color by type; and for records without an impact or a
                 genotype under impact and zygosity)
        color_deletion: [r, g, b] of the deletion type (Color by type; and for records without an impact or a genotype
                 under impact and zygosity)
        color_mnp: [r, g, b] of the MNP type (Color by type; and for records without an impact or a genotype under
                 impact and zygosity)
        color_sv: [r, g, b] of the SV type (Color by type; and for records without an impact or a genotype under
                 impact and zygosity)
        color_cnv: [r, g, b] of the CNV type (Color by type; and for records without an impact or a genotype under
                 impact and zygosity)
        color_complex: [r, g, b] of the complex type (Color by type; and for records without an impact or a genotype
                 under impact and zygosity)
    """
    params: dict = {"name": name}
    if display_mode:
        params["display_mode"] = display_mode
    if color_mode:
        params["color_mode"] = color_mode
    for key, value in (("filter_pass_only", filter_pass_only), ("min_quality", min_quality),
                       ("min_allele_freq", min_allele_freq), ("show_labels", show_labels), ("show_snps", show_snps),
                       ("show_insertions", show_insertions), ("show_deletions", show_deletions),
                       ("show_svs", show_svs), ("show_other", show_other), ("stem_height", stem_height),
                       ("marker_size", marker_size), ("opacity", opacity), ("color_snp", color_snp),
                       ("color_insertion", color_insertion), ("color_deletion", color_deletion),
                       ("color_mnp", color_mnp), ("color_sv", color_sv), ("color_cnv", color_cnv),
                       ("color_complex", color_complex)):
        if value is not None:
            params[key] = value
    return json.dumps(_vx_cmd("set_variant_options", **params))


@mcp.tool()
def vx_set_interaction_options(
    name: str,
    display_mode: str = "",
    color_mode: str = "",
    min_score: float | None = None,
    min_distance: int | None = None,
    intra_chr_only: bool | None = None,
    arc_alpha: float | None = None,
    line_width: float | None = None,
    arc_color: list[int] | None = None,
    low_score_color: list[int] | None = None,
    high_score_color: list[int] | None = None,
    matrix_value: str = "",
    matrix_scale: str = "",
    matrix_bin: int | None = None,
    matrix_tads: bool | None = None,
    matrix_loops: str | None = None,
    matrix_filters: bool | None = None,
) -> str:
    """Configure display options for an interaction track (BEDPE).

    Only provided parameters are changed. Every value is checked before anything changes: a
    word not among those below, a switch that is not true or false, a number out of range, a
    colour that is not [r, g, b] with each 0 to 255, or a key the command does not read is
    refused by name, and nothing is changed (since 0.11.0). An open track panel row shows the
    new values.

    The answer gives interaction (opacity as drawn, customOpacity) and, since 0.11.0, matrix, as vx_get_state
    gives it.

    Args:
        name: Track name (as shown in vx_get_state)
        display_mode: Display style: "arcs", "heatmap", "links", "matrix" (since 0.11.0: the contacts binned, each
                      pair of bins a square above the axis; the matrix_ keys below)
        color_mode: Color mapping: "score", "distance", "solid"
        min_score: Minimum interaction score filter, 0 to 1e9 (the Matrix display applies it with matrix_filters
                   true, its default, since 0.11.0)
        min_distance: The least distance in whole bases between a loop's two anchors on one chromosome, 0 to 1e9;
                   closer loops are not drawn (since 0.11.0; the Matrix display applies it with matrix_filters
                   true, its default)
        intra_chr_only: Only show intra-chromosomal interactions; off, a loop to another
                        chromosome is drawn at its anchor, labelled with that chromosome
        arc_alpha: The track's own opacity, 0.1 to 1, kept on both colour schemes and in
                   the session; without it a loops track is drawn at its scheme's
                   opacity, 0.5 on the light scheme and 0.7 on the dark. The answer
                   gives interaction: opacity (as drawn) and customOpacity
        line_width: Line thickness in pixels, 0.5 to 10
        arc_color: [r, g, b] of the loops in the "solid" colour mode; it leaves the score
                   colours as the scheme draws them
        low_score_color: [r, g, b] of the score ramp's low end ("score" colour mode), the track's own on both schemes;
                   the other end keeps the colour the scheme in use draws
        high_score_color: [r, g, b] of the score ramp's high end ("score" colour mode), the track's own on both
                   schemes; the other end keeps the colour the scheme in use draws
        matrix_value: The Matrix display's colour (since 0.11.0): "count", "balanced" (balanced by iterative
                   correction as cooler balances one chromosome, with the Contact Matrix analysis's defaults:
                   the same numbers as vx_run_analysis ContactMatrix at the same resolution; a masked bin's
                   squares are grey) or "obs_exp" (observed over expected, a diverging ramp on log2 from 1/4 to
                   4; no value, so grey, on the first two diagonals)
        matrix_scale: "linear" or "log", the colour scale of counts and balanced values
        matrix_bin: The bin in whole bases, 0 to 100,000,000 (0: chosen by the zoom, a pixel or more a bin)
        matrix_tads: Outline the domains between TAD Boundary Detection's boundaries
        matrix_loops: An interaction track of the group whose loops are ringed over the matrix ("" for none)
        matrix_filters: "Apply filters" of the Matrix display (since 0.11.0): true (the default) bins the contacts the
                   track's Min score and min_distance keep, as vx_run_analysis ContactMatrix does by default; false
                   every contact, the numbers of ContactMatrix with apply_track_filters "false"
    """
    params: dict = {"name": name}
    if display_mode:
        params["display_mode"] = display_mode
    if color_mode:
        params["color_mode"] = color_mode
    for key, value in (("min_score", min_score), ("min_distance", min_distance), ("intra_chr_only", intra_chr_only),
                       ("arc_alpha", arc_alpha),
                       ("line_width", line_width), ("arc_color", arc_color), ("low_score_color", low_score_color),
                       ("high_score_color", high_score_color), ("matrix_bin", matrix_bin),
                       ("matrix_tads", matrix_tads), ("matrix_loops", matrix_loops),
                       ("matrix_filters", matrix_filters)):
        if value is not None:
            params[key] = value
    for key, value in (("matrix_value", matrix_value), ("matrix_scale", matrix_scale)):
        if value:
            params[key] = value
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
    strip_height: float | None = None,
    strip_expanded_height: float | None = None,
    mod_strip_height: float | None = None,
    polya_strip_height: float | None = None,
    mutation_strip_height: float | None = None,
    mod_strip_expanded_height: float | None = None,
    polya_strip_expanded_height: float | None = None,
    mutation_strip_expanded_height: float | None = None,
    expand_mod_strip: bool | None = None,
    expand_polya_strip: bool | None = None,
    expand_mutation_strip: bool | None = None,
    mod_strip: dict | None = None,
    polya_strip: dict | None = None,
    mutation_strip: dict | None = None,
    open_strip_as_track: str = "",
    reads_are_rna: bool | str | None = None,
    mod_colours: dict | None = None,
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
    display_mode: str = "",
    matrix_codes: list[str] | str | None = None,
    matrix_cells: str = "",
    matrix_min_modified: int = 0,
    group_by_site: dict | str | None = None,
    sort_by_site: dict | str | None = None,
    max_reads: int | None = None,
    subsetting: bool | None = None,
    min_mapq: int | None = None,
    show_soft_clips: bool | None = None,
    show_hard_clips: bool | None = None,
    show_quality_scores: bool | None = None,
    show_directionality: bool | None = None,
    show_coverage: bool | None = None,
    coverage_log_scale: bool | None = None,
    coverage_scale: str = "",
    coverage_auto_scale: bool | None = None,
    coverage_y_min: float | None = None,
    coverage_y_max: float | None = None,
    coverage_proportion: float | None = None,
    coverage_color_mode: str = "",
    mod_mark_style: str = "",
    reset_colours: bool | None = None,
) -> str:
    """Configure display options for an alignment track (BAM).

    Only provided parameters are changed; others keep their current values.

    The four rate-line colour keys of 0.10.0 (mut_agg_total_line_color, mut_agg_sub_line_color,
    mut_agg_del_line_color, mut_agg_ins_line_color) are no longer parameters of this tool, and the HTTP command
    refuses them by name since 0.11.0: the mutation strip, a view of the variant summary, draws no rate lines;
    mut_agg_color_* colour it and mutation_strip {"display": "line"} draws a line through its sites.

    The answer's options give strip_height, strip_expanded_height, the six own heights, expand_mod_strip,
    expand_polya_strip, expand_mutation_strip, reads_are_rna (as decided), reads_are_rna_set (auto, rna or dna),
    mod_colours, mod_colour_overrides and strips (each strip's kind, shown, expanded, height as laid out,
    own_height, own_expanded_height, lane_count and drawn (the lanes' plot boxes and axes the last frame drew); its
    view's counting, counted window or null, message, and its series, tails or, for the mutation strip, sites,
    sites_passing and options); vx_get_state gives each alignment track's strips too.

    The read layout (keys such as sort_by, sort_order, group_by, packing and the filter_ ones): filters, then groups,
    then the sort within each group, each group packed into rows of its own under a labelled band; the filters apply as
    the reads load, before the max-reads subsample; a bad value fails the call and names its key.

    The options of the track panel's alignment section (the keys from max_reads to reset_colours). A bad value refuses
    the request and names the key; the reply's `options` holds every option of the track as it stands (send the name
    alone to read them).

    Args:
        name: Track name (as shown in vx_get_state)
        show_unique_primary: the three class switches, filters of the read layout since 0.10.0, applied as the reads
            load (before the subsample) so the rows close up; a value that is not true or false is refused by name.
            When every read of the view is hidden the track says so (vx_get_state: readLayout.hidden_all)
        show_multi_primary: the three class switches, filters of the read layout since 0.10.0, applied as the reads
            load (before the subsample) so the rows close up; a value that is not true or false is refused by name.
            When every read of the view is hidden the track says so (vx_get_state: readLayout.hidden_all)
        show_multi_secondary: the three class switches, filters of the read layout since 0.10.0, applied as the reads
            load (before the subsample) so the rows close up; a value that is not true or false is refused by name.
            When every read of the view is hidden the track says so (vx_get_state: readLayout.hidden_all)
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
        show_base_modifications: The MM/ML calls on the reads: diamonds at densities 1 and 2, thin ticks (one per row
            and pixel column, the most probable call's) at 3 and 4 (since 0.11.0)
        show_mod_summary_strip: The modification summary strip above the reads (every call of the reads held at or
            above mod_prob_threshold), on its own switch whatever show_base_modifications says (since 0.11.0)
        mod_prob_threshold: The marks' and the summary strip's least probability, a whole number 0-255 (the ML value;
            128 is 0.5; default 128); any other value is refused by name (since 0.11.0). The modification strip has
            its own call cutoff (mod_strip's call_cutoff, 0.70 by default), which this value does not change
        show_polya_tail: The poly(A) tail (Dorado pt tag) beyond the read's 3' end: to its length at full detail, up
            to 600 px (since 0.11.0), a fixed width below
        show_mod_aggregator: The modification strip: a compact view of the modification density track's counting
            (every primary record in view) above the reads (since 0.11.0)
        show_polya_aggregator: The poly(A) strip: a compact view of the poly(A) tail track's counting (since 0.11.0)
        show_mutation_aggregator: The mutation strip: a compact view of the variant summary's counting (every primary
            record in view against the group's reference: the sites that pass its thresholds, each with a p (binomial,
            or Fisher's against a control: mutation_strip's test and control) and a Benjamini-Hochberg q; since
            0.11.0; until then a mismatch rate of the reads held); it needs the group's reference, and it counts views
            up to 5 Mb (mutation_strip's max_span; a wider view says to zoom in; a session keeps its own)
        strip_height: A compact strip's height in px, 16-200 (default 32): the height the three strips share unless a
            strip has its own
        strip_expanded_height: An expanded strip's height in px, 24-600 (default 120; never below the compact height):
            the height the three strips share unless a strip has its own
        mod_strip_height: the modification strip's own compact height in px, 0 (the shared strip_height) or 16-200
            (since 0.11.0); anything else is refused by name
        polya_strip_height: the poly(A) strip's own compact height in px, 0 (the shared strip_height) or 16-200
            (since 0.11.0); anything else is refused by name
        mutation_strip_height: the mutation strip's own compact height in px, 0 (the shared strip_height) or 16-200
            (since 0.11.0); anything else is refused by name
        mod_strip_expanded_height: the modification strip's own expanded height in px, 0 (the shared
            strip_expanded_height) or 24-600 (since 0.11.0). A strip split into two lanes or more
            (vx_set_aggregate_options' split, through mod_strip or mutation_strip) is grown, when its height is less,
            to 18 px and 11 px a lane (the demo's four modification codes: 62 px), so that each lane carries its name
        polya_strip_expanded_height: the poly(A) strip's own expanded height in px, 0 (the shared
            strip_expanded_height) or 24-600 (since 0.11.0)
        mutation_strip_expanded_height: the mutation strip's own expanded height in px, 0 (the shared
            strip_expanded_height) or 24-600 (since 0.11.0); a strip split into two lanes or more is grown, when its
            height is less, as mod_strip_expanded_height says
        expand_mod_strip: true expands that strip, false makes it compact (as its chevron or a double click on it)
        expand_polya_strip: true expands that strip, false makes it compact (as its chevron or a double click on it)
        expand_mutation_strip: true expands that strip, false makes it compact (as its chevron or a double click on
            it)
        mod_strip: the options of that strip's view, as vx_set_aggregate_options takes them; checked whole before
            anything changes, a bad one refused by name ("mod_strip: display: bars, line, heat, dots, box, histogram
            or violin"); lift_from as vx_set_aggregate_options takes it: the modification strip counts the calls of
            another isoform's reads on the transcript in view, and vx_get_state gives the strip's lift_from and lift
            under strips (since 0.11.0); min_mapq is refused by name: the strip counts at its track's MAPQ floor, set
            min_mapq on the alignment track (since 0.11.0)
        polya_strip: the options of that strip's view, as vx_set_aggregate_options takes them; checked whole before
            anything changes, a bad one refused by name ("polya_strip: display: bars, box, violin or dots"); min_mapq
            is refused as in mod_strip
        mutation_strip: the options of the mutation strip's view, as vx_set_aggregate_options takes them for a variant
            summary (display, height, changes, min_depth, min_alt_fraction, min_alt_reads, min_base_quality, cutoff_on,
            cutoff, min_alt_per_strand, test, control, ...; its min_mapq is the track's and is refused by name there);
            checked whole before anything changes, a bad one refused by name ("mutation_strip: display: bars, line or
            heat") (since 0.11.0)
        open_strip_as_track: "modifications", "polya" or "mutation" ("variants" too; since 0.11.0): adds an
            aggregate track below this one with every option of that strip's view (the mutation strip's: a variant
            summary), after the other keys; the answer names it (opened_track). Since 0.11.0 also one lane of a
            strip, as "<strip>:<lane>": "modifications:a" (a modification's code, as MM writes it), "mutation:A>G" (one
            substitution) or "mutation:substitution" (the substitutions): the track opens with that lane alone (no
            split); a lane of deletions or insertions, and any lane of the poly(A) strip, is refused by name
        reads_are_rna: true names modifications in RNA words (m6A, m5C, Ψ, I), false in DNA words (6mA, 5mC), "auto"
            as VX finds it (an RNA basecall model in a read group's DS, or transcript references)
        mod_agg_fill_color: the modification strip's single colour [r,g,b] (drawn when mod_strip's colour_mode is
            single)
        mod_agg_line_color: the modification strip's single colour [r,g,b] (drawn when mod_strip's colour_mode is
            single)
        color_5mc: the colour of 5mC in the marks, the summary strip and the legend [r,g,b] (it takes effect since
            0.11.0)
        color_5hmc: the colour of 5hmC in the marks, the summary strip and the legend [r,g,b] (it takes effect since
            0.11.0)
        color_6ma: the colour of 6mA in the marks, the summary strip and the legend [r,g,b] (it takes effect since
            0.11.0)
        color_mod_other: the colour of every other modification in the marks, the summary strip and the legend [r,g,b]
            (it takes effect since 0.11.0)
        mod_colours: {code: [r,g,b] or null}: the colour of any modification by its code ("m", "a", "17802"); null
            gives it back to the palette
        polya_agg_fill_color: the poly(A) strip's colour [r,g,b]
        polya_agg_line_color: the poly(A) strip's colour [r,g,b]
        polya_agg_violin_color: the poly(A) strip's colour [r,g,b]
        mut_agg_color_a: the mutation strip's colour of A [r,g,b], each 0 to 255, else refused by name (since 0.11.0);
            it reaches the strip's view and the variant summary tracks made from this track
        mut_agg_color_c: the mutation strip's colour of C, as mut_agg_color_a
        mut_agg_color_g: the mutation strip's colour of G, as mut_agg_color_a
        mut_agg_color_t: the mutation strip's colour of T, as mut_agg_color_a
        mut_agg_color_del: the mutation strip's colour of deletions, as mut_agg_color_a
        mut_agg_color_ins: the mutation strip's colour of insertions, as mut_agg_color_a
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
        filter_min_length: read length range in bases (0: off)
        filter_max_length: read length range in bases (0: off)
        filter_min_mapq: hide reads below this MAPQ (0: off)
        filter_max_edit_extent: 0 to 1 (1: off)
        filter_min_mod_extent: in the unit of mod_extent_unit (0: off)
        filter_hide_flags: SAM flag bits to hide, as samtools view -F (256
                           secondary, 2048 supplementary, 1024 duplicates)
        reset_layout: true restores the default layout before the other keys
        filter_indegra: "all", "hide_reallocated" (reads without XR kept) or
                        "reallocated_only"; applied as the reads load
        group_by_site: {"by": "base" or "call", "chromosome": ..., "position": 1-based}: the reads grouped by their
            base there (A, C, G, T, N, deletion, insertion, no sequence, not covered) or their call there (modified by
            each code, unmodified, ambiguous, no call, not covered); "none" clears (since 0.11.0)
        sort_by_site: {"by": "base" or "call_probability", "chromosome": ..., "position": 1-based, "code": "a"}: the
            reads sorted by the code's probability on their base there (with sort_order "descending", the most modified
            first) or by their base there (the bases other than the reference's first); the reads without a value there
            come last in either order; "none" clears (since 0.11.0). The position is 1-based, as the ruler writes it;
            a bad value is refused by name.
        display_mode: "reads" (the reads, as before) or "calls_matrix": a row for each read held with a call at a site
            in view, a column for each site of a modification where at least matrix_min_modified reads are called
            modified (at the modification strip's call cutoff), in genomic order; vx_get_state gives the track's
            callsMatrix (columns with position 1-based, code, modification, strand, modified, unmodified, ambiguous;
            read_names and cells, a letter a column: M modified, U unmodified, A ambiguous, - no call, . not covered;
            bands; notes) (since 0.11.0)
        matrix_codes: the modification codes of the matrix's columns ("a", "m", "17802"; a list; "" or "all" for every
            code)
        matrix_cells: "probability" (the code's probability as a colour, the default) or "class" (modified, unmodified,
            ambiguous, no call)
        matrix_min_modified: the least number of reads called modified that makes a site a column, 1-100000 (default 2)
        max_reads: reads kept in view when subsampling is on (0: no cap, at most
                   1000000); the view loads again
        subsetting: keep at most max_reads in view, sampled at random
        min_mapq: reads below this mapping quality are not loaded (0 to 255)
        show_soft_clips: the switches of the panel
        show_hard_clips: the switches of the panel
        show_quality_scores: the switches of the panel
        show_directionality: the switches of the panel
        show_coverage: the switches of the panel
        coverage_log_scale: the switches of the panel; since 0.11.0 true is coverage_scale "log10" and false "linear",
                            read when coverage_scale is not given
        coverage_scale: the coverage strip's value axis (since 0.11.0): "linear", "log2", "log10", "sqrt" or "asinh"
        coverage_auto_scale: true (the default since 0.11.0): the axis is fitted to the depths in view, the largest at
                             95 percent of the height and 0 kept; false: coverage_y_min to coverage_y_max
        coverage_y_min: the bottom of the range drawn while coverage_auto_scale is false, -1e9 to 1e9, the top above
            the bottom (else refused by name); the answer gives it with coverage_axis, the axis the last frame drew
            (bottom, top, scale, fitted, empty, manual_ignored and its view; null before a frame)
        coverage_y_max: the top of that range, -1e9 to 1e9, above the bottom (else refused by name); the answer gives
            it with coverage_axis too, as for coverage_y_min
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
    for key, value in (("display_mode", display_mode), ("matrix_cells", matrix_cells)):
        if value:
            params[key] = value
    if matrix_min_modified:
        params["matrix_min_modified"] = matrix_min_modified
    for key, value in (("matrix_codes", matrix_codes), ("group_by_site", group_by_site),
                       ("sort_by_site", sort_by_site)):
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
    if coverage_scale:
        params["coverage_scale"] = coverage_scale
    if mod_mark_style:
        params["mod_mark_style"] = mod_mark_style
    for key, value in (("strip_height", strip_height), ("strip_expanded_height", strip_expanded_height),
                       ("mod_strip_height", mod_strip_height), ("polya_strip_height", polya_strip_height),
                       ("mutation_strip_height", mutation_strip_height),
                       ("mod_strip_expanded_height", mod_strip_expanded_height),
                       ("polya_strip_expanded_height", polya_strip_expanded_height),
                       ("mutation_strip_expanded_height", mutation_strip_expanded_height),
                       ("coverage_auto_scale", coverage_auto_scale), ("coverage_y_min", coverage_y_min),
                       ("coverage_y_max", coverage_y_max),
                       ("expand_mod_strip", expand_mod_strip), ("expand_polya_strip", expand_polya_strip),
                       ("expand_mutation_strip", expand_mutation_strip), ("mod_strip", mod_strip),
                       ("polya_strip", polya_strip), ("mutation_strip", mutation_strip), ("reads_are_rna", reads_are_rna),
                       ("mod_colours", mod_colours)):
        if value is not None:
            params[key] = value
    if open_strip_as_track:
        params["open_strip_as_track"] = open_strip_as_track
    return json.dumps(_vx_cmd("set_alignment_options", **params))


@mcp.tool()
def vx_add_aggregate_track(source: str, kind: str, options: dict | None = None) -> str:
    """Add a read aggregate track over an alignment track's BAM, in that track's group, just below it.

    Returns the new track's name and its group (and, for a variant summary with min_alt_per_strand set on RNA reads,
    a warning).

    Args:
        source: The alignment track's name (as shown in vx_get_state; any group, the active one first)
        kind: "modifications" (per site, code and strand over every primary read in view: a read's call
              at a base is the most probable of its modifications and the unmodified base, and stands at
              the call cutoff or more, else it is filtered; each site's stoichiometry, p and q), "polya"
              (poly(A) tail lengths per bin, or one bin a sequence) or "variants" (since 0.11.0: per base,
              the reads of A, C, G, T, a deletion and an insertion with their strands against the group's
              reference; the sites that pass the thresholds, each with a binomial p against the base qualities'
              error, or Fisher's against a control track of the group, and a Benjamini-Hochberg q over the sites
              listed in the window counted)
        options: Any option of vx_set_aggregate_options. Every option is read before the track is made:
                 one that is unknown, of another kind or out of range refuses the request by name, and
                 no track is added (since 0.11.0)
    """
    params: dict = {"source": source, "kind": kind}
    if options:
        params.update(options)
    return json.dumps(_vx_cmd("add_aggregate_track", **params))


@mcp.tool()
def vx_set_aggregate_options(name: str, options: dict) -> str:
    """Set the options of a read aggregate track. Every option is read before any is applied: an unknown
    option, one of another kind of track or a value out of range refuses the request by name and
    changes nothing (since 0.11.0); the answer gives the track's options as they stand.

    Modifications: display bars|line|heat|dots|box|histogram|violin (the last four draw the calls'
    probabilities of each site or bin); height stoichiometry|modified|calls|confidence; opacity
    confidence|stoichiometry|significance|none; opacity_floor 0-1; colour_mode by_type|single; colour
    [r,g,b]; code_colours {code: [r,g,b] or null} (null takes a colour away; code_colours null takes them
    all); call_cutoff 0.5-0.99 (default 0.7: a call stands when its probability reaches it, else it is
    filtered; threshold of 0.10.0 is refused); min_coverage 1-100000 (the
    modified and unmodified calls a site needs); strand both|plus|minus; resolution site|window|bins|auto;
    width 1-100000 (nt of a window or a bin); pixel_rule largest|mean (where several sites share a
    pixel); test binomial|fisher; background 0.0001-0.5 (the binomial test's rate, default 0.05); control
    (an alignment track of the group, Fisher's control; "" for none); significance q|p;
    significance_cutoff above 0 to 1 (default q 0.05); significance_saturation 1-300 (-log10 at which a mark is opaque);
    failed_sites faint|hidden; failing_opacity 0-1 (the opacity of a unit that fails the cutoff, apart from the floor:
    0.4 for a new track; the floor, opacity_floor, is 0.55 for a new track and was 0.2 until 0.11.0); split none|code
    (a lane for each modification code, each on its own axis, one count and one q for all the lanes; since 0.11.0);
    codes (the codes drawn: a list, or a text such as "a, 17802"; "", "all" or null for every code); lift_from (since 0.11.0): on a transcriptome BAM, the isoforms whose reads' calls are
    counted on the transcript in view: an isoform's id or transcript name, a list of them, "gene" for every isoform
    of its gene (the transcript in view included), "" for its own reads alone; each call carried through the genome by
    an annotation of the session that places the isoforms on it; the calls on bases the transcript lacks are counted
    apart (vx_get_state's aggregate lift: words, records, off_target, absent_calls).
    Poly(A): display bars|box|violin|dots; statistic median|mean; anchor three_prime|right_end; bin_width
    0-10000000 (0 automatic); min_reads 1-100000; min_length and max_length
    0-100000 (0: no bound); tail_bins bins|sequence (one bin a reference sequence); colour [r,g,b].
    Variants (since 0.11.0): display bars|line|heat; height alt_fraction|alt_count|depth; opacity significance|none;
    opacity_floor 0-1 (0.55 for a new track); failing_opacity 0-1 (the opacity of a site that fails the cutoff, apart
    from the floor: 0.4 for a new track); split none|class|kind (a lane for each class, the substitutions, the
    deletions and the insertions, or for each change, A>G and the rest, del, ins; each lane on its own axis, one
    count and one q for all of them); cutoff_on p|q; cutoff (above 0, at most 1; default q 0.05); opaque_at (the p or
    q drawn opaque, default 1e-10); failing faint|hidden; min_base_quality 0-60 (13); min_depth (10);
    min_alt_fraction 0-1 (0.1); min_alt_reads (3); min_alt_per_strand (a whole number, 0 off by default, 2
    suggested): where a site's reference base has at least this many reads on each strand, the site lists only when
    its main change, of the changes counted the one with the most reads, has as many on each strand, before the test,
    so q is over the sites that list; a site whose reference base has fewer on a strand is not judged and lists
    (counted in strand_unjudged), so reads that lie on one strand, as direct RNA reads do, lose no site; on a track
    whose reads are RNA the answer carries a note saying so (warning); test
    binomial|fisher (Fisher's one-sided exact test of a site's alt and other reads against those of the control
    at the same base; a site where the control has no read is not tested, with no p or q); control (an alignment
    track of the group that reads a BAM: Fisher's control, counted by the same rule over the same window; "" for
    none; a name the group lacks is refused with the code TRACK_NOT_FOUND); changes "all", "substitutions" or a list
    such as "A>G,T>C"; error_model qualities|fixed; error_rate (above 0, below 1; 0.01); vcf_track (a variant
    track of the group; "" for every site); colours {A, C, G, T, deletion, insertion: [r,g,b]}. A key that is not a
    variant summary's is refused by name, and nothing changes unless every key is read.
    All three (since 0.11.0): scale linear|log2|log10|sqrt|asinh; auto_scale (true by default: the height's axis is
    fitted to the units or sites in view that pass the significance cutoff, all of them when none passes, the largest
    at most 95 percent of the height, and a proportion (stoichiometry, confidence, alt fraction) never past 100
    percent); y_min and y_max (the range drawn while auto_scale is false; a y_min or a y_max alone makes the axis
    manual, but a y_max of 0 alone stays automatic, as a poly(A) track's y_max of 0.10.0 was read; a range whose
    top is not above its bottom is refused by name).
    All three: min_mapq 0-255; max_span 1-100000000 bases (1 or more for variants; a new variant summary counts views
    up to 5 Mb, the other kinds 2 Mb; a view counts the view and half its width on each side; a session keeps
    each track's own).

    Args:
        name: The aggregate track's name
        options: The options to change, as above
    """
    params: dict = {"name": name}
    params.update(options or {})
    return json.dumps(_vx_cmd("set_aggregate_options", **params))


@mcp.tool()
def vx_aggregate_rows(name: str, chromosome: str, start: int, end: int, bin_width: int = 0, resolution: str = "",
                      width: int = 0, path: str = "", format: str = "") -> str:
    """The rows a read aggregate track gives a region [start, end) with its options. Modifications: a row a
    unit (start, end, base, code, modification, strand, sites, calls, modified, unmodified, other_mod,
    filtered, stoichiometry, confidence, mean_probability, max_calls, p, q, log10_p, log10_q); poly(A): a
    row a bin (start, end, n, mean, median, q1, q3, lower_whisker, upper_whisker, min, max, outliers,
    bandwidth). Counted on a thread of the viewer's own and answered when done (no client timeout),
    within the track's max_span; the answer states the options the rows were counted under, the records,
    the sites left out, the calls filtered and the units tested (since 0.11.0). A modification's name
    (modification) is in the track's words: m6A, m5C on RNA reads (since 0.11.0). A track with lift_from counts
    its rows through the lift; the answer's lift gives what was lifted.
    For a variant summary (since 0.11.0): one row per listed site (position, 1-based; reference; depth; A, C, G, T,
    del, ins and each one's _forward count; filtered; alt; alt_fraction; error; main_change with main_forward and
    main_reverse, the strand rule's; tested; p; q; log10_p; log10_q, each null for a site not tested; passes; with
    Fisher's test also control_depth, control_alt and control_alt_fraction), q over the region's tested sites (q_over
    says which: "q over the 53 sites listed in chr1:1-2,400"); the answer also gives test, sites_untested,
    strand_filtered, strand_unjudged, strand_rule and control (name, bam, counted, records, problem);
    counted on a thread of the viewer's own as the other kinds' rows are (since 0.11.0), the chromosome found by the
    alignment track's alias rule; bin_width, resolution and width are not read; path also writes the rows as
    tab-separated text (the answer holds them too; the columns are Save rows', ending main_change, main_forward,
    main_reverse and the control's three, NA with no control), tsv being the one format.
    NO_REFERENCE when the track's group has no reference.

    Args:
        name: The aggregate track's name
        chromosome: The region's chromosome (any name the alias rule maps to the BAM's)
        start: The region's first base, 0-based
        end: The region's end, 0-based and exclusive (end - start at most the track's max_span)
        bin_width: As in 0.10.0: modifications 1 a site, more bins of that width; poly(A) bases a bin
                   (0: the track's own, else 100)
        resolution: site, window or bins for modifications (default the track's; auto is read as site)
        width: The window's or the bin's width in nt (default the track's)
        path: Write the rows to this file instead of answering them (a variant summary's rows are answered as well)
        format: tsv (with a path; the default there) or bedmethyl (modifications: a line a site, modkit's
                columns; Ndelete, Ndiff and Nnocall are 0; every site with a modified or unmodified call, a coverage
                floor of 1 as modkit writes it, since 0.11.0; the answer's min_coverage says the floor applied)
    """
    params: dict = {"name": name, "chromosome": chromosome, "start": start, "end": end}
    for k, v in (("bin_width", bin_width), ("resolution", resolution), ("width", width), ("path", path), ("format", format)):
        if v:
            params[k] = v
    # the rows are counted on a thread of the viewer's own and answered when done: no client timeout
    r = _vx_post("/command", {"command": "aggregate_rows", "params": params}, timeout=None)
    return json.dumps(_answer(r))


@mcp.tool()
def vx_add_dti_track(source: str = "", path: str = "") -> str:
    """Add a transcript DTI track (INDEGRA's Direct Transcript Integrity, 0 degraded to
    10 intact) from an INDEGRA alignment track's YD tags (source) or from INDEGRA's
    {sample}_process.txt (path, recognised by its header line).

    Returns the new track's name.

    Args:
        source: An alignment track's name (as shown in vx_get_state)
        path: INDEGRA's process table, absolute path
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
    scale: str = "",
    auto_scale: bool | None = None,
    y_min: float | None = None,
    y_max: float | None = None,
) -> str:
    """Set the options of a transcript DTI track. Every value is checked before anything changes; a word not among
    those below, a switch that is not true or false, a number out of range or a key the command does not read is
    refused by name (INVALID_PARAMS), and a range whose top is not above its bottom, with auto_scale false, is
    refused too (a range of that kind was read as 0 to 10 in silence until 0.11.0).

    Returns the track's state.

    Args:
        name: The DTI track's name
        colour_scale: "sequential" or "diverging"
        value_min: The DTI at the scale's low end (0 to 20; default 0): a name of y_min's, read where y_min is not
                   given
        value_max: The DTI at the scale's high end (0 to 20; default 10): a name of y_max's, read where y_max is not
                   given
        labels: Show the transcript's name and DTI
        scale: The ramp's transform (since 0.11.0): "linear", "log2", "log10", "sqrt" or "asinh"
        auto_scale: true (the default since 0.11.0): the ramp runs from the least DTI of the track's table to its
                    greatest (not the view's, so that a transcriptome's one transcript in view does not always take
                    the ramp's end); false: y_min to y_max
        y_min: The DTI at the ramp's low end while auto_scale is false, -1e9 to 1e9
        y_max: The DTI at the ramp's high end while auto_scale is false, -1e9 to 1e9
    """
    params: dict = {"name": name}
    if colour_scale:
        params["colour_scale"] = colour_scale
    if scale:
        params["scale"] = scale
    for key, value in (("value_min", value_min), ("value_max", value_max), ("labels", labels),
                       ("auto_scale", auto_scale), ("y_min", y_min), ("y_max", y_max)):
        if value is not None:
            params[key] = value
    return json.dumps(_vx_cmd("set_dti_options", **params))


@mcp.tool()
def vx_dti_lookup(name: str, transcript: str) -> str:
    """A transcript's DTI in a DTI track's table, by the rule the read popup
    uses: the exact ID, else the one ID of its base without a version.

    Returns match, id and dti.

    Args:
        name: The DTI track's name
        transcript: A transcript ID, with or without its version
    """
    return json.dumps(_vx_cmd("dti_lookup", name=name, transcript=transcript))


# ═══════════════════════════════════════════════════════════════════════
# Sashimi and Overlay Tracks (tools since 0.11.0)
# ═══════════════════════════════════════════════════════════════════════


@mcp.tool()
def vx_add_sashimi_track(source: str, options: dict | None = None) -> str:
    """Add a Sashimi track over an alignment track's BAM, in that track's group, just below it (since 0.11.0).

    It draws the depth of the reads in view and an arc for each splice junction, counted as Splice Junctions counts
    it.

    Returns the new track's name, its group and its options.

    Args:
        source: The alignment track's name (any group, the active one first); its reads must come from a BAM file
        options: Any option of vx_set_sashimi_options, all read before the track is made: one unknown or out of
                 range refuses the request by name and adds nothing
    """
    params: dict = {"source": source}
    if options:
        params.update(options)
    return json.dumps(_vx_cmd("add_sashimi_track", **params))


@mcp.tool()
def vx_set_sashimi_options(name: str, options: dict) -> str:
    """Set a Sashimi track's options, or a Splice Junctions result track's Sashimi display (since 0.11.0), all or
    nothing; an unknown key or a value out of range is refused by name. The answer gives the track's options as
    they stand.

    Sashimi track: min_count 1 to 1e9 (the least reads of a junction drawn, default 1); arc_scale height|width;
    shared_scale; show_counts; show_profile; profile_color [r,g,b]; profile_opacity 0 to 1 (0.6); line_width 0.5 to
    10 (2); the profile's value axis (since 0.11.0): scale linear|log2|log10|sqrt|asinh, auto_scale (true by default:
    fitted to the depths in view, the largest at 95 percent of the profile's height and 0 kept), y_min and y_max (the
    range drawn while auto_scale is false, -1e9 to 1e9; a top that is not above the bottom is refused by name);
    hide_spanning true|false (false; since 0.11.0, true leaves out of the arcs, the list and the scale the junctions
    whose two ends lie either side of the view; "yes" and 1 are refused by name); and,
    counted again when changed, min_mapq 0 to 255 (the source's floor when the track is made),
    min_overhang 1 to 10000 (8), include_supplementary, max_span 1000 to 10000000 (bases, 2000000; a wider view is
    not counted).
    Junction track: display features|sashimi, min_count, arc_scale, show_counts, hide_spanning (read back as
    sashimi_hide_spanning in vx_get_state's options).

    Args:
        name: The Sashimi track's or the junction track's name
        options: The options to change, as above
    """
    params: dict = {"name": name}
    params.update(options or {})
    return json.dumps(_vx_cmd("set_sashimi_options", **params))


@mcp.tool()
def vx_add_overlay_track(tracks: list[str], name: str = "", options: dict | None = None) -> str:
    """Overlay two or more signal, coverage or alignment tracks of one group in one lane, each in its own colour
    (since 0.11.0); the tracks stay as they are.

    Refused by name, nothing added: a track not found, a type not taken, a name twice, two groups, an option
    refused.

    Returns the new track's name, group and options.

    Args:
        tracks: The names of the tracks to overlay, two or more, of one group
        name: The new track's name (default "Overlay: " and the tracks' names)
        options: Any option of vx_set_overlay_options, all read before the track is made
    """
    params: dict = {"tracks": tracks}
    if name:
        params["name"] = name
    if options:
        params.update(options)
    return json.dumps(_vx_cmd("add_overlay_track", **params))


@mcp.tool()
def vx_set_overlay_options(name: str, options: dict) -> str:
    """Set an overlay track's options, all or nothing (since 0.11.0): shared_scale (true: one axis over every source;
    false: each source on its own axis); scale linear|log2|log10|sqrt|asinh (the value axis's transform, as for every
    other quantitative type: "shared" and "own" are shared_scale's, and refused here by name); auto_scale (true by
    default: fitted to the values in view, the largest at 95 percent of the height and 0 kept); y_min and y_max (the
    range drawn while auto_scale is false, -1e9 to 1e9, the top above the bottom); style line|area; line_width 0.5
    to 10; key; colors (one [r,g,b] a source); opacities (one 0 to 1 a source). The answer gives its options as they
    stand.

    Args:
        name: The overlay track's name
        options: The options to change, as above
    """
    params: dict = {"name": name}
    params.update(options or {})
    return json.dumps(_vx_cmd("set_overlay_options", **params))


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

    Returns, in prose: `hit`, whether an element was under the point; `selectedElements`,
    how many are selected now; `popupVisible` and, when the popup is open, `popupText`,
    its text; `selected`, when exactly one element is selected: its trackName, trackType,
    elementIndex and subIndex (a modification call's index, -1 for the element itself);
    with button 3, `rightClick`: "inform" (the popup) or "menu" (the mouse would open the
    context menu).

    A click on the sequence track selects the base, block of bases or window of the GC curve drawn under it, and
    popupText gives its words (the base and its place, a block's bases, the GC around them or of the window; since
    0.11.0).

    Args:
        x: Horizontal position in the track area, in widget pixels
        y: Vertical position in the track area, in widget pixels
        button: 1 (left, the default) or 3 (right)
        ctrl: With button 1, add to the selection instead of replacing it (the mouse's Ctrl+click,
              Command+click on macOS)
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
    Settings > Capture. Without a path the file goes to the folder Settings > Capture
    names (a Snapshots folder in the settings folder when none is set) under the
    configured name pattern. A scale that the GPU cannot render is lowered to the
    largest it can, and the answer says so (`clamped`).

    Returns, in prose: `path`, the file written; `format`; `width` and `height` in
    pixels; `scale`, the scale used; `clamped`, whether it was lowered; `transparent`,
    whether the file has an alpha channel. A viewer that cannot render answers NOT_READY
    (HTTP 503); a format that is not one of the three is INVALID_PARAMS (HTTP 400).

    Args:
        path: Absolute path of the file to write (its extension names the format when
              `format` is empty)
        format: "png", "jpeg" or "tiff"
        scale: The render scale (a positive number; 1.0 is the screen's resolution)
        transparent: PNG and TIFF only: keep the background transparent (straight alpha)
        include_overlays: Draw the selection and hover overlays too
        jpeg_quality: JPEG only, 1 to 100
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
    """Scroll a track's rows vertically, as the track's own scrollbar does: an alignment track's reads, or
    the rows of a gene, feature or transcript DTI track (since 0.11.0).

    Returns the confirmation message. A track that is not there answers NOT_FOUND (HTTP 404); a track
    whose rows do not scroll (a sequence, coverage, signal, variant, interaction or read aggregate track)
    answers NOT_SUPPORTED (HTTP 400).

    Args:
        name: The track's name (as shown in vx_get_state)
        offset: The scroll position in pixels from the top of the rows (0 is the top; a negative value is
                read as 0; a value past the end scrolls to the bottom, since the renderer clamps it at the
                next frame)
    """
    return json.dumps(_vx_cmd("set_track_scroll", name=name, offset=offset))


# ═══════════════════════════════════════════════════════════════════════
# Analysis Tools
# ═══════════════════════════════════════════════════════════════════════


@mcp.tool()
def vx_list_analyses(tracks: list[str] | None = None) -> str:
    """List available analyses for the currently loaded (or specified) tracks.

    Returns JSON with available analyses grouped by category, including
    name, description, and output format. Since 0.11.0, on a group whose
    reference is read as a transcriptome, the analyses meant for a
    genome (Splice Junctions, CNV Segmentation, Strand Bias, Simple Peak
    Calling, Enrichment Over Input, TAD Boundary Detection, Contact
    Matrix, Contact Frequency vs Distance) are left out of analyses, as
    the Run Analysis dialog leaves them out, and listed apart under
    left_out_for_genome, each with its name, type (the name
    vx_run_analysis takes) and reason; left_out_for_genome is an empty
    list on any other group. vx_run_analysis still runs one named.

    Args:
        tracks: Optional list of track names to check against.
                If omitted, uses all visible tracks. A name that is no
                track of the active group is refused (TRACK_NOT_FOUND,
                HTTP 404, naming it), and a tracks that is not a list of
                names is refused (INVALID_PARAMS), as vx_run_analysis
                refuses them (since 0.11.0; an unknown name used to be
                left out without a word).
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

    Every result file gets a manifest beside it (<result>.manifest.json: the analysis, version, time, each
    input file with size, modification time and SHA-256, the parameters as applied, scope and region, each
    output file with size and SHA-256, the summary, the elapsed seconds); vx_analysis_status's summary names
    it under manifest. An input file above the Settings limit (1024 MB by default) is listed without a hash
    unless params carries hash_inputs: "true" (every input file is checksummed whatever its size).

    Since 0.11.0 a result's tracks (when Settings' Auto-create tracks is on; CNV Segmentation gives two) go right
    below the last of the request's input tracks in the group that holds them, after any result tracks already
    below it; an analysis of the reference alone counts the sequence track as its input, a control or compare track
    is an input too, and a group that holds no input takes them at its end. The window's view scrolls to show them,
    with the input track above them when both fit, when the group is on screen, and vx_get_state lists them there.

    Since 0.11.0, in a reference group without a reference (an empty group made with vx_create_group), an analysis
    that needs the reference (GCContent, NucleotideFrequency, CpGDensity, MotifSearch, RepeatDensity, MismatchRate,
    CodingImpact, OrfPrediction) is refused before it starts, NO_REFERENCE (HTTP 409), naming the analysis and the
    group ("GC Content needs a reference, and the group 'custom' has none (No reference): load a FASTA into the
    group, or switch to a group that has one"). An analysis that vx_list_analyses leaves out on a transcriptome
    group (left_out_for_genome) still runs when named here.

    Returns status and output path on completion.

    Args:
        analysis: Analysis type name, one of the 59 analyses (vx_list_analyses lists
                  those the loaded tracks can take; an unknown name answers
                  UNKNOWN_ANALYSIS, HTTP 400). Common examples: "GCContent", "FeatureCounts",
                  "SignalDifference", "SimplePeakCalling", "MappingQualityDistribution",
                  "CpGDensity", "MotifSearch", "TrackExport".
        tracks: Optional list of track names as input.
                Order matters for A/B analyses (first = A, second = B).
                If omitted, each input of the analysis takes the
                first visible track of a kind it accepts, in the
                order of the analysis's inputs, and a track serves
                one input: a visible track that no input accepts
                is not used, and an input that no visible track
                fits stays empty (the analysis fails with its own
                message if it needs it; when no visible track fits
                any input, the visible tracks are passed on as
                they are). Tracks named are used as given. A name
                that is no track of the active group is refused
                (TRACK_NOT_FOUND, HTTP 404, naming it), and a tracks
                that is not a list of names is refused
                (INVALID_PARAMS); nothing runs (since 0.11.0).
        params: Optional analysis-specific parameters, e.g.
                {"pseudocount": "1.0", "window_size": "100"}.
                Where the analysis runs: {"scope": "viewport"} (the default
                unless Settings says otherwise) is the window in view,
                {"scope": "chromosome"} the whole of the chromosome in view,
                {"scope": "genome"} every chromosome of the input tracks
                ("group" and "all" are read as "genome"). A group's reference
                is a transcriptome or a genome by the group's reference mode
                (vx_set_reference_mode; auto by default): auto reads it as a
                transcriptome when at least half of its sequences are named
                as transcripts (Ensembl's ENST and its forms for every
                species, RefSeq's NM_, NR_, XM_ and XR_, FlyBase's FBtr,
                Trinity's, StringTie's MSTRG., PacBio's PB. and NCBI's rna-
                forms, in any letter case; one sequence alone counts, since
                0.11.0), whatever their lengths; failing that as a genome
                when a sequence reaches 1,000,000 bases (since 0.10.0 such a
                reference is a genome however many sequences it holds,
                unless its names say transcripts) or there are 50 sequences
                or fewer; of more than 50 shorter ones, as a genome when at
                least half are named as contigs, scaffolds or chromosomes
                (since 0.11.0) and as a transcriptome otherwise. On a
                transcriptome
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
                name is the value of Settings, Analysis. A parameter name
                the analysis does not read is not refused:
                vx_analysis_status lists it in parameters_unread (since
                0.11.0).
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
                low MAPQ, duplicate, multimapped that leaves it out). Since
                0.11.0 the four also take "count_fragments": "false" ("true"
                counts each fragment once, as featureCounts -p
                --countReadPairs counts a pair: each read of a pair meets
                genes by the mode on its own strand and votes for each, the
                gene with the most votes takes the fragment, a tie is
                ambiguous; a pair on two chromosomes is paired across them; a
                pair is left out when both reads are below min_mapq, or when
                either is a duplicate with ignore_duplicates, has NH above 1
                without count_multimapped, or failed QC with
                count_qc_failed "false"; FeatureCounts reads the whole BAM on
                a region too), the summary then giving count_unit
                "fragment", fragments_counted, fragments_two_mates,
                fragments_one_mate, fragments_single_end and
                fragments_two_references, and fragments_assigned,
                fragments_other_genes, fragments_no_feature and
                fragments_ambiguous in place of reads_assigned,
                reads_other_genes, reads_no_feature and reads_ambiguous.
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
                Since 0.11.0 SimplePeakCalling, FeatureProminence,
                CoverageAnomalies and VariantDensityHotspots never take a
                window's own background: at viewport scope or on a region the
                background (the cut-off) is that of the chromosome, read
                whole, so a window costs what its chromosome costs, and the
                region lists the peaks, stretches or hotspots of the
                chromosome that meet it, each whole (the hotspots in the
                chromosome's windows from 0); at genome scope the one cut-off
                of FeatureProminence and CoverageAnomalies leaves out the
                organelles' sequences (chrM, MT, M, chrMT, Mito, any name with
                mitochond; the plastid's C, chrC, Pt, chrPt, any name with
                chloroplast or plastid), which are still listed, unless no
                other sequence has a value. The summary's background_from
                names what the background was read over (the chromosome,
                "genome", or "each chromosome" for the peak call and the
                hotspots at genome scope), and organelles_left_out the
                sequences left out.
                MotifSearch: {"motif": the motif to find, required (no
                default; for example "DRACH"), "strand": "both" | "forward"
                | "reverse"} (IUPAC codes, no regular expression; the default
                strand is both on a genome and forward on a transcriptome; a
                site that both strands match is one row, strand ".").
                GCContent: {"window_size": "1000", "step_size": "500"}; with a
                step below the window each value is written over the step at
                its window's centre, so the bedGraph never overlaps; the
                summary's chromosomes is the number of chromosomes written.
                Since 0.11.0 a sequence shorter than a window or bin the
                request does not name (GCContent, NucleotideFrequency,
                CpGDensity and RepeatDensity: Settings' window, 1,000;
                BinStatistics: 10,000; StrandBias, SoftClipFrequency,
                PerBaseMismatchRate and MismatchRate: 1,000) is read in
                windows of a tenth of its length, rounded to 10, at least 50
                (GCContent's step half of it); a window or bin named is kept
                on every sequence. The summary's short_sequences and
                short_sequence_windows say how many sequences took such a
                window and how long it was. VariantDensity and
                VariantDensityHotspots keep their window.
                Since 0.11.0, four RNA-seq analyses (the defaults below are
                Settings > Analysis > RNA-seq's first values; Settings can
                change them). DifferentialExpression
                takes a gene track and two conditions of BAMs: {"condition_a":
                "a1.bam,a2.bam", "condition_b": "b1.bam,b2.bam"} (alignment
                track names, comma-separated; the named tracks are added to
                the inputs; without them, the first two alignment tracks
                given, the first being A), FeatureCounts' parameters above,
                "min_count": "10" (a gene whose counts sum below it is not
                tested), "pseudocount": "0.5", "q_cutoff": "0.05",
                "lfc_cutoff": "1", "count_fragments": "true" (since 0.11.0:
                each fragment once, given to a gene as FeatureCounts gives it
                with count_fragments; "false" counts each read, which
                overstates the evidence of paired data; the summary's
                count_unit says which). With two BAMs or more a condition:
                median-of-ratios size factors and a negative binomial Wald
                test; else the fragments (or reads) counted and an exact
                binomial test (the summary's test and normalisation say
                which). A TSV (gene_id,
                gene_name, a count column a BAM, mean_a, mean_b, log2fc, p, q)
                and a BED track of the genes that pass (significant_file).
                SpliceJunctions: {"min_overhang": "8", "min_count": "1",
                "include_supplementary": "false", "min_mapq": Settings'
                minimum MAPQ}; the loaded reference gives each junction's
                motif and a gene track (optional) says annotated or novel.
                STAR's SJ.out.tab columns with a header and the motif in
                words, and a BED track (junctions_file).
                TranscriptQuantification takes a genome BAM with a gene track,
                or a transcriptome BAM (reads aligned to transcripts, a read's
                secondary alignments joining its class): {"em_tolerance":
                "0.0001", "em_max_rounds": "100000", "fragment_length": "0"
                (0: the pairs' mean insert size, or none for long reads)} and
                FeatureCounts' record parameters (strand, min_mapq,
                primary_only, ignore_duplicates, count_multimapped,
                count_qc_failed). A TSV (transcript_id, gene_id, length,
                effective_length, count, tpm); the summary's em_rounds and
                em_converged.
                GeneBodyCoverage takes the same inputs: {"bins": "100",
                "min_reads": "10", "end_fraction": "0.2"} and the same record
                parameters. A TSV of the profile (percentile, mean_coverage,
                transcripts) and one of the transcripts profiled
                (transcripts_file: transcript_id, reads, ratio_3_5); the
                summary's median_ratio_3_5.
                Since 0.11.0, three analyses of modifications and poly(A)
                tails. ModificationSites takes a BAM with MM/ML tags:
                {"call_cutoff": "0.7" (0.5 to 0.99: a call stands when its
                most probable outcome reaches it, else it is filtered),
                "min_coverage": "5" (the modified and unmodified calls a site
                needs), "min_mapq": Settings' minimum MAPQ, "test": "binomial"
                or "fisher" (fisher when "control" is given), "background":
                "0.05" (the binomial test's rate), "control": the name of a
                control alignment track of the group (Fisher's test),
                "significance": "q" or "p", "significance_cutoff": "0.05"}. A
                TSV (chrom, start, end, strand, base, code, name, calls,
                modified, unmodified, filtered, stoichiometry,
                mean_probability, p, q; with a gene track of the genome on a
                transcriptome BAM also genome_coordinates, "chrom:pos:strand"
                1-based), bedMethyl of every site with a modified or
                unmodified call (bedmethyl_file; a coverage floor of 1, as
                modkit writes it, since 0.11.0; summary bedmethyl_sites) and a
                BED track of the sites that pass (sites_file).
                PolyAStatistics takes a BAM with pt tags and a gene track (the
                reads given to genes by FeatureCounts' parameters above), or a
                transcriptome BAM (one row a transcript): {"short_tail": "50",
                "long_tail": "150", "compare": the name of a second alignment
                track, "min_tails": "10" (the tails each BAM needs for the
                Wilcoxon test)}. A TSV (gene_id and gene_name, or
                transcript_id and gene_id; reads, no_tail, n, mean, median,
                q1, q3, share_short, share_long; with compare the same with
                "_b", then u, p, q).
                ModificationCoOccurrence takes a BAM with MM/ML tags and
                ModificationSites' parameters (its candidates are the sites
                that pass): {"code": a modification's code as MM writes it
                ("a" m6A, "m" 5mC, "17802" pseudouridine, "17596" inosine;
                empty: each code with itself), "code2": a second code (pairs of
                a code site and a code2 site), "max_distance": "1000",
                "min_reads": "10", "max_sites": "1000" (the candidates a
                reference keeps, the most significant), "candidates":
                "significant" or "all", "pair_test": "stratified" (the
                default) or "fisher"; since 0.11.0}. fisher takes the reads as
                independent and their calls as given, so reads whose calls run
                high everywhere make every pair look associated; stratified
                compares reads of a like level (each read's share of modified
                calls at the other candidate sites, four strata; a read with
                fewer than 3 such calls left out), by the
                Cochran-Mantel-Haenszel test and the Mantel-Haenszel common
                odds ratio, q over the pairs with min_reads reads kept, and
                adds the columns reads_0_25, reads_25_50, reads_50_75,
                reads_75_100, reads_left_out, common_odds_ratio, p_stratified
                and q_stratified; the loops are the pairs the chosen test
                passes (summary pair_test, pairs_tested). Use fisher for
                whether two sites are modified on the same molecules at all,
                stratified for whether they are linked beyond each molecule's
                own level. A TSV (chrom, pos1 and pos2 1-based, strand, code1,
                code2, n11, n10, n01, n00, odds_ratio, p, q) and a BEDPE track
                of the pairs that pass (pairs_file).
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
                the window). Since 0.11.0, when the request names no
                window_size and every chromosome of the track is shorter
                than twice the window and a bin (1,050,000 bases at the
                defaults), the window is a quarter of the longest chromosome,
                in bins of a tenth of it unless bin_size is given (bins
                rounded down to 100 bases; a window below 10,000 is not
                fitted): the summary's fitted_window says so, and its
                window_size and bin_size, like the parameters, give what was
                applied.
                OrfPrediction needs the reference loaded and a gene annotation
                among the tracks, or a transcriptome reference alone, whose
                sequences are read as transcripts: {"min_codons": "10",
                "near_cognate": "false", "near_cognate_list": as CodingImpact's,
                "mitochondrial_code": "vertebrate" | "standard",
                "track_cap": "100000"}. Every ORF of
                at least min_codons codons (the start codon and the codons
                before the stop) on each transcript as transcribed, from an ATG
                (with near_cognate, also a codon of the list) to the first stop
                in its frame; columns transcript_id, gene_id, orf_start and
                orf_end (1-based on the transcript, the stop codon included),
                frame (1 to 3), codons, start_codon, kozak (the bases at -3 and
                +4) and class (translon, uORF, upstream_overlapping, extension,
                internal_in_frame, internal_out_of_frame,
                downstream_overlapping, dORF, non_coding, no_annotation,
                unclassified); a BED12 in genome coordinates beside the table
                (summary orfs_file) is the result track. A region lists the ORFs
                whose span on the genome meets the window, each found on its
                whole transcript. The result track holds at most track_cap
                ORFs (Settings' default 100000; 0 every ORF; a negative
                value is refused by name), an equal share of every class:
                the cap is divided equally among the classes with ORFs, a
                class with fewer ORFs than its share keeps them all and what
                it leaves is divided equally among the others again; the
                places the division leaves over go to the classes first in
                the order translon, extension, internal_in_frame, uORF,
                upstream_overlapping, dORF, downstream_overlapping,
                internal_out_of_frame, non_coding, no_annotation,
                unclassified (a cap below the number of classes gives one ORF
                to each of the first); within a class the longer before the
                shorter, ties by a hash of the transcript and the ORF's
                place; the summary gives
                track_orfs and, when the cap cut, track_file (the track's
                BED12 of those kept: orfs_file and the table list every ORF);
                vx_get_state's feature gives capHeld, capListed and capNoun,
                and the track says how many it draws (since 0.11.0).
                CnvSegmentation: a BAM, coverage or signal track and optionally
                a control of those kinds (the second such track, or {"control":
                a track's name}); {"bin_size": "10000", "min_bins": "2",
                "t_threshold": "5", "gain_threshold": "0.2", "loss_threshold":
                "-0.25", "gc_correct": "false", "min_mapq": Settings' floor}.
                Each bin's mean depth over the median of the region's bins with
                depth (and over the control's) as a log2 ratio, -20 for a bin
                without reads; gc_correct (the reference loaded) subtracts a
                rolling median over the bins in order of GC; each chromosome is
                segmented by circular binary segmentation without permutations
                (a split where the largest |t| of the arcs reaches t_threshold,
                each part at least min_bins bins), and each segment called gain,
                loss or neutral by its mean; columns chrom, start, end, bins,
                mean_log2, call; the segments' BED (segments_file) and the bins'
                bedGraph (bins_file) are added as two tracks (the bins' track
                opens on Auto: a bin without reads, -20, is left out of its
                axis and marked at its foot, since 0.11.0). A reference on
                which no input (nor the control) has a read is left out of
                the table, the segments and the bins and counted: the
                summary's references_without_reads and
                references_without_reads_names, the first five then how many
                more (since 0.11.0; each empty reference of a BAM's header
                used to give a loss at -20).
                ContactMatrix: an interaction track (BEDPE; .cool, .mcool and
                .hic files are not read, and vx_load_file refuses them saying
                so); {"resolution": "10000", "weight": "score" | "count",
                "ignore_diags": "2", "min_nnz": "10", "mad_max": "5",
                "tolerance": "1e-5", "max_rounds": "200",
                "apply_track_filters": "true" (since 0.11.0: the
                interactions the input track's Min score and min_distance
                leave out are left out, as the Matrix display's
                matrix_filters does by default; "false" reads every
                interaction; the summary's track_filters and
                interactions_filtered_out say what was applied)}. Each chromosome's
                contacts (anchors at their midpoints, as TADBoundaryDetection
                reads them) binned and balanced alone as cooler 0.10.4 balances
                with cis_only, the expected at each distance as cooltools
                0.7.1's expected_cis; columns chrom, bin1_start, bin2_start,
                count, balanced, obs_exp ("NA" where a bin is masked); the bins'
                biases (biases_file) and the expected (expected_file) beside it;
                no track. On a region, the pairs whose two bins meet the window,
                with the chromosome's numbers.
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
                lines; a CDS that carries NCBI's mark of an open
                5' end, start_range=.,N on the plus strand or
                end_range=N,. on the minus strand, has no start
                whatever else the file says), read as Met whatever
                its codon (Ensembl's initial-Met edit, as VEP
                reads it):
                a change of it is start_lost unless the new
                first codon reads Met (CTG to TTG lost, CTG to
                ATG kept, ATG to ATA kept on chrM), and bases
                put in or taken out at it are read at their
                5'-most placement along the transcript, so that
                both strands give one row for one change: bases
                taken out are read there when that placement meets
                the start codon or lies wholly before it (wholly
                before it, a 5' UTR row; meeting it, read there,
                with translon_pos and codon_change at that
                placement), and bases put in move only when their
                5'-most placement reaches the start's first base,
                where they leave the three start bases intact and
                are a 5' UTR row (no row where the start codon
                begins its exon); bases put in that cannot reach
                it stay where the left alignment put them, and
                inside the start codon they change it (the column
                normalised keeps the left-aligned form). The column translon_pos is the
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
                read as T, read at every run), else "." (a row of
                a translon without a found start, a UTR row, and
                the ref_mismatch, splice, not_translated and
                incomplete_codon rows have "." too); the summary's
                near_cognate_list names the list. A
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
                moved_by_normalisation, ref_mismatch; the keys
                VariantIntersection gives for each call set carry
                _A and _B: moved_by_normalisation_A and _B,
                ref_mismatch_A and _B, no_variant_alleles_A and
                _B, below_min_af_A and _B, unique_A and _B and,
                when there are any, no_reference_sequence_A and
                _B; shared and normalised carry none).
                AlleleFrequencySpectrum counts a frequency in the
                last bin whose lower bound, i over the number of
                bins held as a 32-bit float, is at or below it,
                and prints the bounds with four decimals when the
                number of bins does not divide 100 (two when it
                does), so a printed bound can differ from the one
                the bin follows: at 3 bins the bound 1/3 is held
                as 0.33333334 and printed 0.3333. VariantDensity
                counts a
                record in the window of its first base (summary
                starts_before_region). TsTvRatio on a region: the
                chromosome's row is the whole chromosome's, the last row the
                region's.
        output_path: Optional explicit output file path.
                     If omitted, auto-generates in the Results directory:
                     <analysis>_<input>_<YYYYMMDD_HHMMSS>.<ext> (the input
                     is the track the analysis ran on, or its window or
                     region), and a name already taken (on disk, or by a
                     result of this run) takes _2, _3 and so on before the
                     extension (since 0.11.0); the files written beside a
                     result follow its name.
        results_dir: the directory for this run's result files and manifest; the results directory of
                     Settings otherwise.
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

    Returns JSON with:
    - running: an analysis is in progress (its handler, then the writing of its manifest)
    - stage: current stage description
    - progress: 0.0 to 1.0
    - complete: it has finished: true only with running false, and then success, error,
      output_path, summary (with the manifest) and parameters are given
    - parameters_unread: for an analysis that succeeded, the names the request gave that it did not read
      ([] when it read them all; since 0.11.0); they are ignored, not refused, and the result's
      manifest lists them too
    - cancelled: whether it was cancelled: false for an analysis that succeeded, a cancel that came
      too late to stop it having had no effect (since 0.11.0)
    - elapsed_seconds: wall-clock time since analysis started
    - estimated_remaining_seconds: ETA in seconds (absent if unknown)

    A failed analysis is answered with HTTP 200 since 0.11.0 (500 before): complete true, success false and its
    error.
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

    Returns JSON with path; header (a table's column names, a VCF's #CHROM names; [] for a BED or
    bedGraph); rows (each line split on tabs; lines starting with '#', blank lines and a BED or
    bedGraph's track line are not rows); offset; returned; next_offset (the offset of the next page,
    only when more rows follow); bytes (the file's size) and bytes_read; cut_rows (rows longer than
    64 KiB, given cut at that length), when there are any. The file is read from its start to the end
    of the page, never whole.

    Args:
        path: the result file (output_path from vx_analysis_status); a relative path is read under
              the results directory.
        offset: the first row to give, counted from 0 (default 0).
        limit: how many rows to give, 1 to 1000 (default 100).
    """
    # the answer comes when the read ends (a page far into a large file reads every line before it): no client timeout
    r = _vx_post("/command", {"command": "read_result_rows",
                              "params": {"path": path, "offset": offset, "limit": limit}}, timeout=None)
    return json.dumps(_answer(r))


# ═══════════════════════════════════════════════════════════════════════
# Circular View and Dot Plot Tools
# ═══════════════════════════════════════════════════════════════════════


@mcp.tool()
def vx_open_circular_view(sequence: str = "", rings: list[str] | None = None, labels: bool | None = None,
                          ruler: bool | None = None, chords: bool | None = None, legend: bool | None = None) -> str:
    """Open the circular view: one sequence of the reference drawn as a circle, in a window of its own.

    For a sequence of up to 20,000,000 bases. Base 0 is at the top, positions run clockwise. Each track of the group
    in view gives a ring in the group's order: genes and features as arcs, coverage, signals and read depth as
    profiles, the GC content, variants as ticks by class, modification sites as ticks by modification as opaque as
    their stoichiometry (on sequences up to 2,000,000 bases); reads in pieces (an SA tag) are chords: back-splices,
    forward splits, strand switches. The linear view's region is marked. Rings read from files are counted on a
    thread of the viewer's own: the answer comes at once, counting true until they land (vx_get_state's circularView
    follows them). Since 0.11.0.

    Returns JSON with view: sequence, length, rings (title, track, kind, shown, counting, items, note), chords
    (counts by kind and the 50 best supported, 0-based from and to), counting, lengthCap, the switches and the
    layout. Refused: headless (INVALID_STATE), no reference (NO_REFERENCE), an unknown sequence
    (CHROMOSOME_NOT_FOUND), a sequence above 20,000,000 bases or a bad key or value (INVALID_PARAMS, named).

    Args:
        sequence: the sequence (default: the one in view); an alias is read as the reference names it.
        rings: the rings to show, by track name or ring title (default: the first ten rings of visible tracks
               that have something on the sequence).
        labels: arcs' names (default true).
        ruler: the ruler (default true).
        chords: the chords (default true).
        legend: the legend (default true).
    """
    params: dict = {}
    if sequence:
        params["sequence"] = sequence
    if rings is not None:
        params["rings"] = rings
    for key, value in (("labels", labels), ("ruler", ruler), ("chords", chords), ("legend", legend)):
        if value is not None:
            params[key] = value
    return json.dumps(_vx_cmd("open_circular_view", **params))


@mcp.tool()
def vx_export_circular_view(path: str, sequence: str = "", rings: list[str] | None = None,
                            width: float | None = None, height: float | None = None, scale: float | None = None,
                            labels: bool | None = None, ruler: bool | None = None, chords: bool | None = None,
                            legend: bool | None = None) -> str:
    """Write the circular view of a sequence to an SVG or PNG file, with a window or headless.

    Draws what the window draws (see vx_open_circular_view): the open window's view when it shows that sequence,
    has finished counting and no rings are named; else the rings are gathered and counted afresh. The answer comes
    when the file is written (no client timeout). Since 0.11.0.

    Returns JSON with path, format, width, height, scale and view (sequence, length, rings, chords). Refused: a
    path not .svg or .png, a size, scale, key or value out of range, a sequence above 20,000,000 bases
    (INVALID_PARAMS, named); NO_REFERENCE; CHROMOSOME_NOT_FOUND; a file not written (IO_ERROR).

    Args:
        path: the file; its extension, .svg or .png, names the format.
        sequence: the sequence (default: the open window's, else the one in view).
        rings: the rings to show, by track name or ring title (default: as the window shows them).
        width: the image's width in logical pixels, 200 to 8,000 (default 1,200).
        height: the image's height in logical pixels, 200 to 8,000 (default 900).
        scale: a PNG's pixels per logical pixel, 0.25 to 8 (default 1); the PNG is opaque.
        labels: arcs' names, as in vx_open_circular_view.
        ruler: the ruler, as in vx_open_circular_view.
        chords: the chords, as in vx_open_circular_view.
        legend: the legend, as in vx_open_circular_view.
    """
    params: dict = {"path": path}
    if sequence:
        params["sequence"] = sequence
    if rings is not None:
        params["rings"] = rings
    for key, value in (("width", width), ("height", height), ("scale", scale), ("labels", labels),
                       ("ruler", ruler), ("chords", chords), ("legend", legend)):
        if value is not None:
            params[key] = value
    # the answer comes when the image is written (the rings read from files are counted first): no client timeout
    r = _vx_post("/command", {"command": "export_circular_view", "params": params}, timeout=None)
    return json.dumps(_answer(r))


@mcp.tool()
def vx_dot_plot(path: str, x: str = "", y: str = "", transcript: str = "", word: int | None = None,
                width: float | None = None, height: float | None = None, scale: float | None = None,
                open: bool | None = None) -> str:
    """Plot one sequence against another by exact word matches and write the plot to an SVG or PNG file.

    A region against itself (repeats beside the diagonal, inversions across it), against another region, or a
    transcript (read 5' to 3') against its gene's region (its exons as steps). Words match forward when they are the
    same bases (case ignored) and in reverse when one is the other's reverse complement; a word with a letter other
    than A, C, G or T matches nothing. Forward blue, reverse complement red; X across, Y down from the top left. Up
    to 100,000 bases a side and 2,000,000 matches the matches are runs; beyond, counted in at most 1,000 x 1,000
    cells; a sequence above 2,000,000 bases is refused. Counted on a thread of the viewer's own; the answer comes when
    the file is written (no client timeout). Since 0.11.0.

    Returns JSON with path, format, title, x and y (name, chromosome, start, end, length, transcript), word, binned,
    forwardMatches, reverseMatches, runs, cell sizes when binned, the caps and opened. Refused: a bad key, word,
    path, region or length (INVALID_PARAMS, named); NO_REFERENCE; GENE_NOT_FOUND; a file not written (IO_ERROR).

    Args:
        path: the file; its extension, .svg or .png, names the format.
        x: "chromosome:start-end" (0-based, end excluded) or a sequence's name; needed unless a transcript is named.
        y: another region (default: x; with a transcript, its gene's region).
        transcript: a transcript by id (with or without version) or name, or a gene (its longest transcript).
        word: 4 to 31 (default 12).
        width: the image's width in logical pixels, 200 to 8,000 (default 900).
        height: the image's height in logical pixels, 200 to 8,000 (default 900).
        scale: a PNG's pixels per logical pixel, 0.25 to 8 (default 1); the PNG is opaque.
        open: show the plot in the dot plot's dialog too (with a window).
    """
    params: dict = {"path": path}
    for key, value in (("x", x), ("y", y), ("transcript", transcript)):
        if value:
            params[key] = value
    for key, value in (("word", word), ("width", width), ("height", height), ("scale", scale), ("open", open)):
        if value is not None:
            params[key] = value
    # the matches are counted on a thread of the viewer's own, the answer when the file is written: no client timeout
    r = _vx_post("/command", {"command": "dot_plot", "params": params}, timeout=None)
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
        output_path: Directory for the output file (default: the folder Settings > Capture
            names for videos, a Snapshots folder in the settings folder when none is set)
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

    Returns JSON with:
    - status: "stopped"
    - frames: the number of frames written
    - elapsed: the recording's length as MM:SS
    - output_path: the video file written

    With no recording in progress the answer is INVALID_STATE (HTTP 409).
    """
    return json.dumps(_vx_cmd("stop_recording"))


@mcp.tool()
def vx_recording_status() -> str:
    """Check the current status of video recording.

    Returns JSON with:
    - ffmpeg_available: whether ffmpeg was found on the system PATH
    - recording: whether a recording is currently active
    - elapsed: elapsed time string (MM:SS) if recording
    - frames: number of frames captured so far if recording
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

    Case "builtin" makes VX's built-in demo again (the two groups "Demo Data - genome" and "Demo Data -
    transcriptome" a window shows at its first start), with a window or headless: its files in the cache
    directory's demo-synth-v3 folder are checked against their manifest and written again when one is
    missing or differs (since 0.11.0 on a thread of their own: the window draws and answers meanwhile), the
    groups are made, the genome group is made active and, with navigate, the view goes to the demo's first
    view. The answer comes when the demo is made (this tool waits for it, with no client timeout): the folder,
    whether the files were written and why, their number and bytes, the time, and the groups, with made true;
    a request made while the window's first start makes the demo waits for that making. When the demo's two
    groups are open already (made at a window's start, or by an earlier call) and no making runs, the call keeps
    them as they are, with what was changed in them, makes the genome group active and, with navigate, goes to
    the demo's first view, and answers at once: made false, written false, no reasons (since 0.11.0; to make the
    demo afresh, remove its groups first with vx_remove_group). vx_loading_status reports "Preparing
    the built-in demo" while the files are made, then done (since 0.11.0), unless a file load is running,
    finishing or queued. Since 0.11.0 the demo's genes and transcripts carry the names and Ensembl identifiers
    of real human genes (the sequence and the reads stay synthetic), so vx_known_features answers on them.
    Since 0.11.0 too, the viewport says "Preparing the built-in demo" while the files are made at a window's
    first start, and, once this version's files are checked, the folders of the demo's earlier versions
    (demo-synth-v1, demo-synth-v2 and their unfinished .part folders) are removed from VX's own cache
    directory, nothing else being touched (a cache folder named through VX_DEMO_SYNTH_CACHE is left alone).

    The answer comes at once (the case, its zip, address, sizes, state in the cache, folder, load
    order and view); then poll vx_loading_status until isLoading is false and done is true: it
    reports the download's stage and progress, and its "demo" entry the job (phase, bytes, files,
    error). Refused: an unknown case (400 INVALID_PARAMS, with the list), another case still being
    opened (409 BUSY), an address that is not http or https (409 INVALID_STATE).

    Args:
        case: "1", "2", "3a", "3b" or "4", or "builtin" for the built-in demo; empty lists the cases,
            their sizes and whether each is in the cache, and opens nothing
        navigate: go to the view of the case's figure once its files are loaded (default True)
    """
    if not case:
        return json.dumps(_vx_cmd("demo_status"), indent=2)
    if case == "builtin":
        # the answer comes when the demo is made (its files are checked, and written when they must be, on a thread
        # of the viewer's own): no client timeout
        r = _vx_post("/command", {"command": "load_demo", "params": {"case": case, "navigate": navigate}},
                     timeout=None)
        return json.dumps(_answer(r))
    return json.dumps(_vx_cmd("load_demo", case=case, navigate=navigate))


# ─── Known Features ─────────────────────────────────────────────────────

@mcp.tool()
def vx_known_features(id: str, species: str = "", kind: str = "", label: str = "", refresh: bool = False) -> str:
    """Open (or show) the Known Features tab of a gene, transcript or protein, in the pane at the right of the window.

    VX asks public services in the background (Ensembl, UniProt, STRING, IntAct when turned on, RCSB PDB, NCBI Gene) for
    the description, location, cross-references, protein, gene summary, interaction partners and the alpha-carbon trace
    of a PDB structure; only the identifier, the species and VX's name and version are sent. Answers at once (tab: its
    key; state: fetching or queued); poll vx_known_features_status(tab) until state is done. Refused: an id that is no
    identifier or gene name (400 INVALID_PARAMS), 32 tabs open (409 BUSY).

    Args:
        id: Ensembl gene, transcript or protein ID (a version is dropped), yeast systematic name, FlyBase or WormBase
            gene ID, UniProt accession, RefSeq transcript or protein, NCBI Gene ID, HGNC ID, or a gene's name
        species: Ensembl's species name for a gene's name (homo_sapiens, ...); default: the id's own, else Settings'
        kind: "symbol" reads an ID-like text as a gene's name; default: the id's own kind
        label: the tab's name (64 characters at most)
        refresh: ask every service again, whatever the age of the answers kept
    """
    params = {"id": id, "refresh": refresh}
    params.update({k: v for k, v in (("species", species), ("kind", kind), ("label", label)) if v})
    return json.dumps(_vx_cmd("known_features", **params))


@mcp.tool()
def vx_known_features_status(id: str = "") -> str:
    """With id (a tab's key, identifier, title or label): that tab whole, as Export JSON writes it (title, description,
    location, ids, crossReferences with links, protein, gene, interactions, structure with its trace as [x, y, z,
    residue], pdbEntries, sources: each service's outcome fetched, cached, cached_after_failure, not_cached, failed or
    not_asked with its time and note; state: queued, fetching, done or cancelled; status). Without id: the options,
    whether the pane is shown, the tab shown, and each tab in short. A tab not open: 404 TAB_NOT_FOUND."""
    return json.dumps(_vx_cmd("known_features_status", **({"id": id} if id else {})), indent=2)


@mcp.tool()
def vx_close_known_features(id: str = "", all: bool = False) -> str:
    """Close a Known Features tab (id: its key, identifier, title or label), or every tab (all=True); the pane hides
    with the last, and its width is kept for the next."""
    return json.dumps(_vx_cmd("close_known_features", **({"all": True} if all else {"id": id})))


@mcp.tool()
def vx_export_known_features(id: str, path: str, format: str = "") -> str:
    """Write a Known Features tab: format "markdown" (its text with links) or "json" (as vx_known_features_status gives
    it, the trace included); by default by the path's extension (.md, .markdown, .json). A relative path is under
    Settings' results directory."""
    return json.dumps(_vx_cmd("export_known_features", id=id, path=path, **({"format": format} if format else {})))


@mcp.tool()
def vx_set_known_features_options(sources: list[str] | None = None, enabled: dict | None = None, species: str = "",
                                  interactions: int = 0, cache_days: int = -1, cache_only: bool | None = None) -> str:
    """Settings > Known Features, saved at once; every value is checked before any is applied, a bad one refused by
    name (400 INVALID_PARAMS). Returns the options as they now are.

    Args:
        sources: all six keys in the new order: ensembl, uniprot, string, intact, pdb, ncbi
        enabled: services on or off, e.g. {"intact": true}
        species: the species of a gene's name, Ensembl's form (homo_sapiens)
        interactions: partners shown a service, 1 to 50
        cache_days: days an answer is kept, 0 to 365 (0: ask every time)
        cache_only: true makes no request at all
    """
    params = {k: v for k, v in (("sources", sources), ("enabled", enabled), ("cache_only", cache_only)) if v is not None}
    params.update({k: v for k, v in (("species", species), ("interactions", interactions)) if v})
    if cache_days >= 0:
        params["cache_days"] = cache_days
    return json.dumps(_vx_cmd("set_known_features_options", **params))


# ─── Sessions ───────────────────────────────────────────────────────────

@mcp.tool()
def vx_save_session(path: str) -> str:
    """Write the session to a .vxs file.

    The file holds the view, the display settings, every group's tracks with their settings (the demo's
    tracks by name: reopening the session makes the demo again), the result tracks with their files and the
    bookmarks, and since 0.11.0 each group's edit log, its reference mode, each bookmark's group and the open
    Known Features tabs; a relative path is under the Sessions directory, and .vxs is appended when missing.
    Returns the path written.

    Args:
        path: The .vxs file to write (absolute, or relative to the Sessions directory; .vxs appended when
            missing)
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
    restored: group, track, reason; since 0.11.0 also a read aggregate track whose settings name no kind this
    version makes) and the status line; the files load in the background
    (vx_loading_status, vx_get_state). Since 0.11.0 each group's edits are applied again after its files load,
    and the Known Features tabs are filled from the cache, without asking the services.

    Args:
        path: The .vxs file to restore (absolute, or relative to the Sessions directory)
    """
    return json.dumps(_vx_cmd("load_session", path=path))


@mcp.tool()
def vx_shutdown() -> str:
    """End the viewer: it answers, then, with a window, saves the window's size, closes it and quits, or, without a
    window, quits. The process has ended 5 s after the answer at the latest (since 0.10.0), even with a dialog left
    open or work still running."""
    return json.dumps(_vx_cmd("shutdown"))


# ─── Edit Mode ──────────────────────────────────────────────────────────

@mcp.tool()
def vx_edit_feature(
    operation: str,
    kind: str = "",
    track: str = "",
    gene_id: str = "",
    transcript_id: str = "",
    exon_number: int | None = None,
    chromosome: str = "",
    gene_start: int | None = None,
    start: int | None = None,
    end: int | None = None,
    name: str = "",
    strand: str = "",
    biotype: str = "",
    by: int | None = None,
    to: int | None = None,
    new_start: int | None = None,
    new_end: int | None = None,
    new_name: str = "",
    exons: list[list[int]] | None = None,
    translon: list[int] | None = None,
    score: float | None = None,
) -> str:
    """Edit the annotation of the active group: add, move, resize, delete or rename a gene,
    transcript, exon or feature, or set a gene's strand or biotype (since 0.11.0).

    Coordinates are 0-based with the end past the last base, as vx_get_genes gives them.
    Every operation is undoable (vx_edit_history) and kept by a saved session.

    A gene whose id is on two sequences (Liftoff's copies) is edited copy by copy (since 0.11.0): give the
    gene's sequence as chromosome (for add_transcript and add_exon too), and, for a transcript or exon whose
    transcript_id is in two genes of one sequence, gene_id as well, and for one of the copies of an id on one
    sequence gene_start, the copy's present start; the keys given narrow the candidates, none left is refused
    FEATURE_NOT_FOUND, several left INVALID_PARAMS naming the key to give.

    An edited transcript is put in order: exons numbered in the order of transcription, its
    span its exons', its translon segments the parts of its exons inside its translon, phases
    by GTF's rule. A value that cannot be meant is refused by name and nothing changes; an
    annotation read through its index (a file above 50 MiB) is not editable in this version.
    The answer gives the operation's index, its description, the log's length and position
    and the gene or feature as it now is.

    Args:
        operation: add_gene, add_transcript, add_exon, add_feature, move, resize, delete,
                   rename, set_strand or set_biotype
        kind: For move, resize, delete, rename, set_strand, set_biotype: the item, one of
              gene, transcript, exon, feature
        track: The annotation track (as named in vx_get_state). May be left out for a gene,
               transcript or exon when the group has one gene track held in memory; required
               for a feature. add_feature with a name the group lacks makes a feature track.
        gene_id: The gene (kind gene; add_transcript's gene; add_gene's new id, default VXEDIT<n>);
                 for kind transcript or exon and add_exon, the transcript's gene, needed when its
                 transcript_id is in two genes of one sequence
        transcript_id: The transcript (kind transcript or exon; add_exon's transcript;
                       add_transcript's or add_gene's new transcript id)
        exon_number: The exon's number in its transcript (kind exon), 1 the 5'-most
        chromosome: add_gene's and add_feature's sequence, and a feature's present sequence (kind feature); for kind
            gene, transcript or exon, add_transcript and add_exon, the gene's sequence, needed when its gene_id is on
            two sequences (Liftoff's copies), else the edit is refused by name (since 0.11.0)
        gene_start: For kind gene, transcript or exon, add_transcript and add_exon: the present start of the gene
            (0-based, as vx_get_genes gives it) naming one of the copies of its id on one sequence (Liftoff's);
            needed when the id has two genes there (since 0.11.0)
        start: add_gene's and add_feature's span start, add_exon's span start, and a feature's present span start
            (kind feature)
        end: add_gene's and add_feature's span end, add_exon's span end, and a feature's present span end (kind
            feature)
        name: The new item's name (add_*); a feature's name when two share its span
        strand: "+", "-" or "." (add_gene, add_feature, set_strand)
        biotype: add_gene's biotype (default protein_coding); set_biotype's
        by: move by this many bases (signed); or
        to: move so that the item starts here
        new_start: resize: the new start (either or both of new_start and new_end)
        new_end: resize: the new end (either or both of new_start and new_end)
        new_name: rename: the gene's or transcript's name, the exon's id, the feature's name
        exons: add_transcript: [[start, end], ...], one at least, none overlapping
        translon: add_transcript: [start, end] of the translon (optional); its segments are
                  the parts of the exons inside it, its UTRs the parts outside
        score: add_feature: the feature's score (optional)
    """
    params: dict = {}
    for key, value in (("kind", kind), ("track", track), ("gene_id", gene_id), ("transcript_id", transcript_id),
                       ("chromosome", chromosome), ("name", name), ("strand", strand), ("biotype", biotype),
                       ("new_name", new_name)):
        if value:
            params[key] = value
    for key, value in (("exon_number", exon_number), ("gene_start", gene_start), ("start", start), ("end", end),
                       ("by", by), ("to", to),
                       ("new_start", new_start), ("new_end", new_end), ("exons", exons), ("translon", translon),
                       ("score", score)):
        if value is not None:
            params[key] = value
    commands = {"add_gene": "edit_add_gene", "add_transcript": "edit_add_transcript", "add_exon": "edit_add_exon",
                "add_feature": "edit_add_feature", "move": "edit_move", "resize": "edit_resize",
                "delete": "edit_delete", "rename": "edit_rename", "set_strand": "edit_set_strand",
                "set_biotype": "edit_set_biotype"}
    if operation not in commands:
        return json.dumps({"error": "operation: one of " + ", ".join(commands), "code": "INVALID_PARAMS"})
    return json.dumps(_vx_cmd(commands[operation], **params))


@mcp.tool()
def vx_edit_bases(
    operation: str,
    chromosome: str,
    position: int | None = None,
    start: int | None = None,
    end: int | None = None,
    bases: str = "",
) -> str:
    """Insert, delete or replace bases of the active group's reference (since 0.11.0).

    Every later coordinate of the sequence moves with the edit, on every track VX holds in
    memory (gene annotation read whole, features, variants, bedGraph and Wiggle signals,
    coverage, interactions). A variant whose reference bases the edit changes is dropped
    while the edit stands. Tracks read from their file on demand (BAM alignments, read
    aggregates, BigWig, an annotation read through its index) hold the original coordinates:
    they are drawn only before the first changed position, with a note.

    A replacement of d bases by n changes coordinates by n - d at its end. The answer gives
    the sequence's new length, its first changed position, and for each track the items
    moved and dropped.

    Args:
        operation: insert, delete or replace
        chromosome: The sequence (as the reference names it)
        position: insert: the new bases go before the base at this 0-based position (the
                  sequence's length appends)
        start: delete and replace: the range's start, 0-based
        end: delete and replace: the range's end, 0-based, past the last base
        bases: insert and replace: IUPAC letters (ACGTN, RYKMSWBDHV), at most 10,000,000
    """
    params: dict = {"chromosome": chromosome}
    if position is not None:
        params["position"] = position
    if start is not None:
        params["start"] = start
    if end is not None:
        params["end"] = end
    if bases:
        params["bases"] = bases
    commands = {"insert": "edit_insert_bases", "delete": "edit_delete_bases", "replace": "edit_replace_bases"}
    if operation not in commands:
        return json.dumps({"error": "operation: one of insert, delete, replace", "code": "INVALID_PARAMS"})
    return json.dumps(_vx_cmd(commands[operation], **params))


@mcp.tool()
def vx_edit_history(action: str, steps: int = 1) -> str:
    """The active group's edit log: list, undo, redo or discard (since 0.11.0).

    The answer gives the log's length and position; undo and redo name the operations they
    undid or redid. A new edit after an undo drops the operations undone.

    Args:
        action: list (every operation with its description and whether it is applied),
                undo, redo, or discard (undo every edit and empty the log; it cannot be
                brought back)
        steps: undo and redo: how many operations, 1 to 1000
    """
    commands = {"list": "edit_list", "undo": "edit_undo", "redo": "edit_redo", "discard": "edit_discard"}
    if action not in commands:
        return json.dumps({"error": "action: one of list, undo, redo, discard", "code": "INVALID_PARAMS"})
    params: dict = {"steps": steps} if action in ("undo", "redo") else {}
    return json.dumps(_vx_cmd(commands[action], **params))


@mcp.tool()
def vx_edit_write(
    fasta: str = "",
    annotation: str = "",
    features: str = "",
    track: str = "",
    feature_track: str = "",
    format: str = "",
    overwrite: bool = False,
) -> str:
    """Write the active group's edited reference and annotation (since 0.11.0). Give one
    path or more, each absolute.

    The answer gives each path written and the counts of sequences, bases, genes,
    transcripts, exons and features. A saved session keeps the paths.

    Args:
        fasta: The edited reference, every sequence in the chromosome list's order, 60 bases
               a line, with its .fai beside it
        annotation: A gene track as GTF (.gtf) or GFF3 (.gff3, .gff), with its gene index
                    (.gidx) built beside it; VX loads it back as the edited model. In a GFF3 a
                    gene or transcript ID that two of them have (a gene's copies on two
                    chromosomes) is written <ID>@<chromosome>, so that each ID is once in the
                    file; the GTF keeps the gene_id (since 0.11.0)
        features: A feature track as BED
        track: The gene track to write (default: the edited one, else the group's only one)
        feature_track: The feature track to write (default: the edited one)
        format: gtf or gff3, when the annotation's name ends in neither
        overwrite: Replace files that are there (otherwise such a path is refused)
    """
    params: dict = {}
    for key, value in (("fasta", fasta), ("annotation", annotation), ("features", features), ("track", track),
                       ("feature_track", feature_track), ("format", format)):
        if value:
            params[key] = value
    if overwrite:
        params["overwrite"] = True
    return json.dumps(_vx_cmd("edit_write", **params))


# ─── Entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--sse" in sys.argv:
        mcp.run(transport="sse")
    else:
        mcp.run()
