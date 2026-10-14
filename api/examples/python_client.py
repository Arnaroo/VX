#!/usr/bin/env python3
"""
python_client.py: minimal zero-dependency Python client for the VX HTTP API.

Uses only the standard library (urllib + json). Designed to be a drop-in
example you can copy into a notebook or script. The official MCP server
(`../../mcp/vx_mcp_server.py`) is the full production client and uses
httpx + fastmcp; this file is the lightest possible alternative.

An error answer carries an HTTP status (4xx or 5xx) with a JSON body holding
`error` and `code`; this client returns that body like any other answer, so
check an answer for `code`.

Run with VX already open. Example:
    python3 python_client.py
"""

from __future__ import annotations

import json
import time
from typing import Any
from urllib import error, request

VX_BASE = "http://127.0.0.1:9876"


# ── HTTP helpers ────────────────────────────────────────────────────────

def _send(req: request.Request, timeout: float | None = 30) -> tuple[int, bytes]:
    """The answer's HTTP status and body, whatever the status (an error's body is JSON too)."""
    try:
        with request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except error.HTTPError as e:
        return e.code, e.read()


def _http_get(path: str) -> tuple[int, bytes]:
    return _send(request.Request(f"{VX_BASE}{path}"))


def _http_post(path: str, body: dict[str, Any], timeout: float | None = 30) -> tuple[int, bytes]:
    data = json.dumps(body).encode("utf-8")
    req = request.Request(
        f"{VX_BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return _send(req, timeout)


# ── Client wrapper ──────────────────────────────────────────────────────

class VXClient:
    """Tiny wrapper over the VX HTTP API."""

    def ping(self) -> dict:
        return json.loads(_http_get("/ping")[1])

    def state(self) -> dict:
        return json.loads(_http_get("/state")[1])

    def cmd(self, command: str, _timeout: float | None = 30, **params: Any) -> dict:
        """Dispatch a generic /command with the given params; the answer's JSON body.

        next_coverage_region and read_result_rows answer when their work ends: give them
        _timeout=None (no limit)."""
        return json.loads(_http_post("/command", {"command": command, "params": params}, _timeout)[1])

    def screenshot(self, target: str = "viewport", scale: float = 1.0) -> bytes:
        """Return raw PNG bytes ("viewport" or "full"); raise with the API's answer when it is refused."""
        path = f"/screenshot/{target}"
        if scale != 1.0:
            path += f"?scale={scale}"
        status, body = _http_get(path)
        if status != 200:
            raise RuntimeError(f"capture refused (HTTP {status}): {body.decode('utf-8', 'replace')}")
        return body

    # ── Convenience wrappers ───────────────────────────────────────────

    def load_file(self, path: str, wait: bool = True) -> dict:
        r = self.cmd("load_file", path=path)
        if wait and "code" not in r:
            self.wait_for_load()
        return r

    def wait_for_load(self, poll_seconds: float = 0.5, timeout: float = 120.0) -> dict:
        """Poll loading_status until the loads are in: done, not finalizing, nothing queued."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            status = self.cmd("loading_status")
            if status.get("done") and not status.get("finalizing") and not status.get("queued"):
                return status
            time.sleep(poll_seconds)
        raise TimeoutError("Load did not complete within timeout")

    def navigate(self, chromosome: str, start: int, end: int) -> dict:
        return self.cmd("navigate", chromosome=chromosome, start=start, end=end)

    def list_chromosomes(self) -> dict:
        return self.cmd("list_chromosomes")

    def search_genes(self, query: str) -> dict:
        return self.cmd("search_genes", query=query)

    def get_sequence(self, chromosome: str, start: int, end: int) -> dict:
        return self.cmd("get_sequence", chromosome=chromosome, start=start, end=end)


# ── Demo ────────────────────────────────────────────────────────────────

def main() -> None:
    vx = VXClient()

    # 1. liveness
    print("ping:", vx.ping())

    # 2. snapshot of current state
    state = vx.state()
    print("active group:", state.get("activeGroup"))
    print("chromosome:", state.get("chromosome"))
    print("viewport:", state.get("viewStart"), "..", state.get("viewEnd"))
    print("tracks:", [t["name"] for t in state.get("tracks", [])])

    # 3. navigate to BRCA1 (chr17, hg38)
    nav = vx.navigate("chr17", 43_044_295, 43_125_483)
    print("navigate:", nav)
    if "code" in nav:
        # e.g. NOT_FOUND (HTTP 404): the loaded reference has no chr17
        print("stopping here:", nav["code"], nav.get("error"))
        return

    # 4. fetch the first 200 bases of the new viewport
    seq = vx.get_sequence("chr17", 43_044_295, 43_044_495)
    print("sequence[0:80]:", seq["sequence"][:80] if "sequence" in seq else seq)

    # 5. screenshot of just the viewport at 2× resolution
    png = vx.screenshot("viewport", scale=2.0)
    out = "/tmp/vx_viewport.png"
    with open(out, "wb") as f:
        f.write(png)
    print(f"screenshot:", out, f"({len(png)} bytes)")


if __name__ == "__main__":
    try:
        main()
    except error.URLError as e:
        raise SystemExit(
            f"Cannot reach VX at {VX_BASE}: is VX running? ({e})"
        )
