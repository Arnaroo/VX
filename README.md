# VX Genome Viewer

> A desktop genome browser for visualising and analysing genomic
> data — sequences, gene annotations, read alignments, signal tracks,
> variants, chromatin interactions. Built with D + GTK3 + OpenGL,
> with hardware-accelerated level-of-detail rendering and an embedded
> HTTP API for AI-assisted exploration.

**Status:** Pre-release (v0.9.0 "Aardvark") — see
[`CHANGELOG.md`](CHANGELOG.md). This is the **public release
repository**: pre-compiled binaries, MCP server source, HTTP API
spec, and end-user documentation.

The VX D source code is **proprietary and confidential**; only
the artefacts in this repository are publicly redistributable.

---

## Get the binaries

Pre-compiled binaries for Linux, macOS (Apple Silicon), and
Windows are attached to each tagged release under the
[**Releases**](https://github.com/Arnaroo/VX/releases) tab.

| Platform | Asset | License |
|---|---|---|
| Linux x86_64 (v3 baseline) | `VX-X.Y.Z-linux-x86_64.tar.gz` | CC-BY-NC-ND-4.0 |
| macOS arm64 | `VX-X.Y.Z-macos-arm64.dmg` | CC-BY-NC-ND-4.0 |
| Windows x86_64 | `VX-X.Y.Z-windows-x86_64-setup.exe` (or `.zip`) | CC-BY-NC-ND-4.0 |

Each release asset has an accompanying `.sha256` checksum file.
Verify before running:

```bash
sha256sum -c VX-X.Y.Z-linux-x86_64.tar.gz.sha256        # Linux
shasum -a 256 -c VX-X.Y.Z-macos-arm64.dmg.sha256        # macOS
certUtil -hashfile VX-X.Y.Z-windows-x86_64-setup.exe SHA256  # Windows
```

---

## Repository layout

| Folder | What's in it | License |
|---|---|---|
| [`mcp/`](mcp/) | MCP server (Python) for AI agents — Claude Code, etc. | **MIT** |
| [`api/`](api/) | HTTP API specification (`openapi.yaml`) + examples | **MIT** |
| [`docs/`](docs/) | User guide, file format guide, troubleshooting, screenshots | **CC-BY-4.0** |
| [`binaries/`](binaries/) | Notes on the release asset format + verification | **CC-BY-4.0** |

See each subdirectory's `LICENSE` file for the precise terms.

---

## Use VX via MCP (AI agents)

VX exposes a 39-tool MCP catalogue covering observation, navigation,
file loading, track management, data queries, export, bookmarks,
analysis, video recording, and runtime configuration. See
[`mcp/INSTALL.md`](mcp/INSTALL.md) for setup.

```bash
# Install
pip install httpx fastmcp

# Run the MCP server (talks to a running VX on 127.0.0.1:9876)
python mcp/vx_mcp_server.py
```

---

## Use VX directly via HTTP

Every MCP tool is also a plain HTTP endpoint on `127.0.0.1:9876`.
See [`api/openapi.yaml`](api/openapi.yaml) for the full schema and
[`api/examples/`](api/examples/) for curl, Python, and Claude
recipes.

```bash
curl -s http://127.0.0.1:9876/ping
# {"status":"ok","app":"VX Genome Viewer","api_version":2}
```

---

## Source code

The D source for VX itself is **not distributed**. It is held
under a proprietary license by Biocodecs Group / Arnaroo
Ribologicals.

The MCP server (`mcp/`) and the API specification (`api/`) ARE
open source under MIT and can be reused freely.

For commercial licensing of the VX source, contact
[hello@biocodecs.org](mailto:hello@biocodecs.org).

---

## Citing

If you use VX in research, please cite:

```
[Citation placeholder — DOI will be added on manuscript publication.
A Zenodo DOI will also be minted automatically for each tagged
release; see the GitHub release page for the live DOI badge.]
```

---

## Build provenance

For full transparency on how each release binary was produced,
see [`docs/BUILD_PROVENANCE.md`](docs/BUILD_PROVENANCE.md).
