# VX Genome Viewer — Troubleshooting

Common problems and their fixes. If your issue isn't listed,
please open an issue on the GitHub repository with the OS,
VX version, and (if possible) the contents of the diagnostic
log described at the bottom.

---

## 1. The window opens but I see a blank black viewport

Most likely an OpenGL initialisation failure.

- VX needs **OpenGL 3.3** or newer. Check your GPU + driver
  combination supports it (`glxinfo | grep "OpenGL version"` on
  Linux).
- On Linux, missing Mesa drivers cause this. Install
  `mesa-libGL` (Fedora) / `libgl1-mesa-glx` (Debian/Ubuntu) /
  `mesa` (Arch/Manjaro).
- On Windows, ensure the latest GPU driver from Intel/AMD/NVIDIA
  is installed. The Microsoft Basic Display Adapter cannot run
  VX.
- On macOS, OpenGL is deprecated but still works through macOS
  15. macOS 26+ is untested.

Set `VX_DEBUG_GL=1` and re-run from a terminal to capture
OpenGL errors:

```bash
VX_DEBUG_GL=1 ./bin/genome-viewer 2>/tmp/vx_gl.log
```

The file `/tmp/vx_gl.log` will contain the GL error trail.

---

## 2. The window has no borders and I can't resize it

VX uses a borderless window with custom decorations. Edge-resize
works by detecting where in the window the cursor is. If
edge-resize doesn't behave on your window manager:

- Try toggling **Settings → Appearance → Use native window
  decorations** (then restart VX).
- Capture the diagnostic trace:

```bash
VX_DEBUG_EDGE_RESIZE=1 ./bin/genome-viewer 2>/tmp/vx_edge.log
```

and attach the relevant tail of `/tmp/vx_edge.log` to a bug
report.

---

## 3. The first BAM region is very slow to load

This is a known limitation on very large BAMs (≈ 23 GB and up).
The first navigate into a chromosome may take ~2 minutes; later
regions on the same chromosome are fast.

- Make sure your BAM has an index next to it
  (`samtools index your.bam` produces `your.bam.bai`).
- The progress strip at the bottom of the window shows you that
  VX is in fact working, not frozen.
- To capture timing for a bug report:

```bash
VX_DEBUG_ALIGNMENT=1 ./bin/genome-viewer 2>/tmp/vx_align.log
```

---

## 4. The alignment track always says "subsampled"

By default VX caps the number of reads it draws to 500 per
visible window. When the actual pile-up exceeds this, you'll
see a small badge on the track.

- Raise the cap via the track's options popover
  (`max_reads`).
- Or via the MCP tool / HTTP API:
  `vx_set_alignment_options(track_name=..., max_reads=5000)`.
- The trade-off is rendering cost: 50,000 reads at 1 px each is
  fine; at 30 px each on a wide screen, it can stutter.

---

## 5. Region search can't find a gene I know is in the file

- Make sure the GTF file is loaded into the **active group**.
- Try the bare gene symbol (`BRCA1`) — not `gene:BRCA1` or
  similar prefixed forms.
- If your GTF lacks the `gene_name` attribute, VX falls back to
  `gene_id`. Try the Ensembl identifier (`ENSG…`).

---

## 6. Drag-and-drop track reorder doesn't show a drop line

If you see no drop indicator at all when dragging a track row,
you may be on a pre-v0.9.0 build — confirm with
`./bin/genome-viewer --version`.

---

## 7. MCP / HTTP API isn't responding

`curl -s http://127.0.0.1:9876/ping` is the canonical liveness
test.

- If you get **"connection refused"**: VX isn't running, or
  another process owns port 9876, or your firewall blocks
  localhost ports. Check `ss -ltnp | grep 9876` (Linux) /
  `lsof -i :9876` (macOS).
- If you get a response from a different app: another VX
  instance is running. Only the first one to start wins the
  port.
- If `ping` works but specific commands hang: capture a
  diagnostic trace with all three flags enabled
  (`VX_DEBUG_GL=1 VX_DEBUG_ALIGNMENT=1 VX_DEBUG_EDGE_RESIZE=1`)
  and attach to a bug report.

---

## 8. Video recording fails with "ffmpeg not found"

VX records by piping raw frames to `ffmpeg`. It must be on
`PATH`:

- Linux: `sudo pacman -S ffmpeg` / `sudo apt install ffmpeg`.
- macOS: `brew install ffmpeg`.
- Windows: download a static build from the official ffmpeg
  releases page and add the folder to your `PATH`.

---

## 9. Fonts look wrong or are missing

VX uses FreeType for text rendering and fontconfig to discover
system fonts. On a fresh container or VM without fontconfig
caches, glyphs may fall back to a default font.

- Linux: install `fontconfig` and a font package
  (`ttf-dejavu` / `fonts-dejavu-core`), then run `fc-cache -f`.
- macOS / Windows: fonts ship with the OS and this rarely
  bites.

---

## 10. Capturing a full diagnostic log

The single recommended invocation:

```bash
VX_DEBUG_GL=1 VX_DEBUG_EDGE_RESIZE=1 VX_DEBUG_ALIGNMENT=1 \
  ./bin/genome-viewer 2>/tmp/vx_dbg.log
```

Reproduce your issue, then attach the tail of `/tmp/vx_dbg.log`
to a bug report. In production VX is silent on stdout/stderr by
design — these `VX_DEBUG_*` env flags are the supported way to
get diagnostic output.

---

## 11. Reporting bugs

Open an issue on the GitHub repository with:

- VX version (`./bin/genome-viewer --version`),
- OS + version,
- the steps to reproduce,
- the diagnostic log tail (above),
- (if relevant) a small sample of the input file that triggers
  the issue.

Please **do not** attach proprietary or PII-containing data to
public issues. Trim or anonymise samples first.
