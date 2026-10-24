# VX: Troubleshooting

Common problems and their fixes. If your issue isn't listed,
please open an issue on the GitHub repository with the OS, the
VX version, and the log file of the run (section 10).

---

## 1. The window opens but I see a blank black viewport

Most likely an OpenGL initialisation failure.

- VX needs **OpenGL 3.3** or newer. Check your GPU and driver
  support it (`glxinfo | grep "OpenGL version"` on Linux).
- On Linux, a missing OpenGL driver causes this. Install Mesa's
  drivers: `mesa-dri-drivers` (Fedora), `libgl1-mesa-dri`
  (Debian, Ubuntu), `mesa` (Arch).
- On Windows, install the current GPU driver from Intel, AMD or
  NVIDIA. The Microsoft Basic Display Adapter does not offer
  OpenGL 3.3.
- On macOS, VX draws its viewport with Apple's OpenGL, which
  Apple has deprecated but macOS 26 still provides.

Set `VX_DEBUG_GL=1` and run VX from a terminal to capture the
OpenGL context's version, renderer and profile, and any OpenGL
errors:

```bash
VX_DEBUG_GL=1 ./bin/vx 2>/tmp/vx_gl.log
```

---

## 2. The window has no borders and I can't resize it

On Linux and Windows VX draws its own window buttons (at the
right of the header bar) and resizes from a strip a few pixels
wide along each edge of the window. On macOS the system's title
bar is used. If edge resizing doesn't behave on your window
manager:

- use the header bar's maximise button, or your window manager's
  own keys; Settings > Appearance > Display can start VX
  maximised;
- capture the diagnostic trace:

```bash
VX_DEBUG_EDGE_RESIZE=1 ./bin/vx 2>/tmp/vx_edge.log
```

and attach the relevant tail of `/tmp/vx_edge.log` to a bug
report.

---

## 3. The first BAM region is very slow to load

This is a known limitation on very large BAMs (about 23 GB and
up). The first navigate into a chromosome may take about two
minutes; later regions on the same chromosome are fast.

- Make sure your BAM has an index next to it
  (`samtools index your.bam` produces `your.bam.bai`).
- The load-status strip at the bottom of the viewport shows you
  that VX is in fact working, not frozen.
- To capture timing for a bug report:

```bash
VX_DEBUG_ALIGNMENT=1 ./bin/vx 2>/tmp/vx_align.log
```

---

## 4. The alignment track always says it is subsampled

By default an alignment track keeps at most 500 reads of a view
(*Max reads*). When the view holds more, a badge `kept/total` is
drawn in the track's label column.

- Raise the cap, or turn subsampling off, in the track's settings
  (Reads).
- Or via the MCP tool / HTTP API:
  `vx_set_alignment_options(name=..., max_reads=5000)` (0 is no
  cap, 1,000,000 the most).
- The trade-off is drawing: in the automatic density mode a view
  that holds more than 20,000 reads is drawn as its coverage strip
  alone; the track's *Density* control fixes a level.

---

## 5. Region search can't find a gene I know is in the file

- Make sure the annotation file is loaded into the **active
  group**.
- Try the gene's name (`BRCA1`) or its ID (`ENSG…`): the search
  matches part of a name or an ID, whatever the case, and lists up
  to 100 genes.
- A gene's name is its `gene_name` attribute, else its `Name`
  (GFF3), else its ID. Since 0.11.0 a gene whose ID is on two
  chromosomes, or twice apart on one (Liftoff's copies), is two
  genes, and the search lists each, shown with its chromosome in
  brackets ("ATCG00150 (ChrC)") or, beside another copy on its
  chromosome, with its chromosome and first base ("ATMG01360
  (Chr2:3,591,778)").

---

## 6. A second VX does not open

Starting VX while it runs brings the running window forward, and
the new process exits (it says so on the terminal it was started
from). To run a second VX, set `VX_NEW_INSTANCE=1` and give it an
API port of its own, since one port serves one VX:

```bash
VX_NEW_INSTANCE=1 ./bin/vx --port 9877
```

The MCP server reaches that one when `VX_API_BASE` is set to
`http://127.0.0.1:9877`.

---

## 7. MCP / HTTP API isn't responding

`curl -s http://127.0.0.1:9876/ping` is the canonical liveness
test.

- If you get **"connection refused"**: VX isn't running, its API
  is off (Settings > MCP / API), it listens on another port
  (Settings > MCP / API, or `--port`), or another process owns
  port 9876. Check `ss -ltnp | grep 9876` (Linux) /
  `lsof -i :9876` (macOS).
- An error answer comes with an HTTP status and a JSON body
  (`error`, `code`, `details`): read the body. A `403` with
  `FORBIDDEN_ORIGIN` (since 0.11.0) means the request looked like
  one a web browser sends for a page: it carried an `Origin`
  header, a `Host` header other than `127.0.0.1`, `localhost` or
  `[::1]`, or a `Sec-Fetch-Site` header other than `none`. Send it
  from a script, `curl` or the MCP server, which send none of
  these. A `504` with
  `TIMEOUT` means the window did not answer in time (Settings >
  Appearance > Performance, API timeout, 30 s by default); the
  command may still have been carried out, so ask for `/state`.
- If `ping` works but specific commands hang: capture the log at
  debug level (section 10) and attach it to a bug report.

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

VX draws the viewport's text with FreeType. By default it and the
information popups use DejaVu Sans Mono from the `fonts` folder
that comes with VX (or the file named by the `VX_FONT_FILE`
environment variable); Settings > Appearance > Fonts chooses
other fonts. The rest of the window's text is drawn by GTK with
the system's fonts.

- Move VX's folder as a whole (on Linux, keep `bin/` and `fonts/`
  side by side).
- Linux: install `fontconfig` and a font package (`ttf-dejavu` /
  `fonts-dejavu-core`).
- `VX_DEBUG_FONT=1` reports on the terminal which fontconfig
  library loaded and where each font came from.

---

## 10. Capturing a full diagnostic log

Each run writes a log file, named by its start time and process
id, in `~/.local/state/vx/` on Linux (`$XDG_STATE_HOME/vx/` when
that is set), `~/Library/Logs/VX/` on macOS and
`%LOCALAPPDATA%\VX\logs\` on Windows. The last 10 are kept, and
one file stops at 64 MiB. By default it holds errors and
warnings; Settings > Paths > Log File shows this run's file and
sets its level.

For everything, at debug level, in the file and on the terminal:

```bash
VX_VERBOSITY=t3l3 ./bin/vx 2>/tmp/vx_dbg.log
```

(`--verbosity t3l3` does the same.) The `VX_DEBUG_*` flags above
add their own traces. In production VX is silent on stdout and
stderr by design.

---

## 11. The chromosome bands do not show

The Bands switch draws UCSC's chromosome bands for a reference
read as a genome whose file or folder name names an assembly UCSC
knows (GRCh38, hg19, GRCm39, mm10 and the like). VX reads a
`cytoBand.txt` beside the FASTA or in its parent folder first,
then its cache directory's copy; else it fetches the table on a
thread of its own and keeps it in its cache directory, and the
bands appear when it arrives (since 0.11.0).

- A reference read as a transcriptome has no bands; check its
  Reference mode in the left panel.
- The fetch needs libcurl and the network; put UCSC's
  `cytoBand.txt` for the assembly beside the FASTA otherwise. A
  mirror can be named with the `VX_CYTOBAND_BASE_URL` environment
  variable.

---

## 12. A `.cool`, `.mcool` or `.hic` file does not load

VX reads contacts from BEDPE files only, and refuses these
formats with the reason. Write the contacts as BEDPE (for a
cooler file, `cooler dump --join`) and load that: an interaction
track draws them as arcs or, in its Matrix display, binned and
balanced, and Contact Matrix computes the same matrix.

---

## 13. The Known Features pane stays empty

Each tab's *Sources* lines say what each service did: fetched,
from the cache, not asked (and why), or failed (and why).

- Settings > Known Features: a service turned off, or *Use the
  cache only* on, asks nothing.
- The requests need libcurl and the network (each waits 20 s at
  most). A session's restored tabs are filled from the cache
  alone; press *Refresh* to ask again.
- A gene's name is looked up in the species of Settings > Known
  Features; an Ensembl, FlyBase or WormBase ID names its own.

---

## 14. Reporting bugs

Open an issue on the GitHub repository with:

- VX version (`./bin/vx --version`),
- OS + version,
- the steps to reproduce,
- the log file of the run (section 10),
- (if relevant) a small sample of the input file that triggers
  the issue.

Please **do not** attach proprietary or PII-containing data to
public issues. Trim or anonymise samples first.
