# VX: User Guide

This guide walks through the most common workflows in VX 0.11.0.
For a quick reference, see [`KEYBOARD_SHORTCUTS.md`](KEYBOARD_SHORTCUTS.md);
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
- **Toolbar** (below it): snapshot, SVG export and recording; the
  circular view and the dot plot; zoom out, fit and zoom in;
  moving the selected track up or down; track height, text scale
  and track scale; the switches for gene detail, intron collapse,
  chromosome bands and the grid.
- **Left panel**: *Reference Groups* (the active group, its
  *Reference mode*, Load Reference, Retrieve Reference), then three
  tabs: **Controls** (the chromosome and its aliases, start and
  end, the coverage navigation, zoom, Quick Navigation with the
  bookmarks, the loaded data), **Tracks** (the track panel) and
  **Edit** (the Edit mode). Toggle the panel with **F9**.
- **Viewport** (centre): the OpenGL drawing area, with the
  chromosome's overview bar and the ruler above the tracks.
- **Known Features pane** (right): opens when you open a Known
  Features tab (section 13) and is hidden while none is open.
- **Load-status strip** (bottom of the viewport): what is loading
  (a file, a region's reads), its progress, and whether it ended
  or failed.
- **Status bar** (bottom of the window): messages, the progress of
  analyses, and a counter of errors and warnings when there are
  any.

![VX main window (VX 0.9.0)](screenshots/07_multi_track.png)

---

## 2. Opening data

When it starts with a window, VX shows two demo groups,
"Demo Data - genome" and "Demo Data - transcriptome", made from
synthetic files it writes once into its cache directory; their
bookmarks go to each feature the demo was made to show.

VX recognises a file by its extension. Open one from the header
bar's **Open** menu, with **Load Reference** in the left panel (a
FASTA), with `Ctrl+O` (a reference genome), through the API's
`load_file` command (the MCP tool `vx_load_file`), or at start
with `--load`, once per file, in order:

```bash
./bin/vx --load my_reference.fa --load annotations.gtf --load reads.bam
```

**Open > Open Demo Dataset** downloads one of the demo datasets
of the paper's case studies once, checks it, and opens it at the
view of its figure.

A reference FASTA creates a new **group**. Annotation, alignment,
signal, variant and interaction files are added to the **active
group**: switch groups in the left panel's *Reference Groups*.
Chromosome names are matched between files that write them
differently (`chr1`, `1`, `NC_000001.11`) by an alias resolver.

Each group's **Reference mode** says how its reference is read:
*Auto* (the default) reads it as a transcriptome when at least
half of its sequences are named as transcripts (ENST, NM_ and the
like); otherwise as a genome when a sequence is 1 Mb or longer or
there are 50 sequences or fewer, and, of more than 50 shorter
ones, as a genome when at least half are named as contigs,
scaffolds or chromosomes, else as a transcriptome. *Genome* and
*Transcriptome* say it yourself. The overview, the analyses' scope
words, the analyses' defaults that depend on it and the
modifications' RNA or DNA names follow it, and the left panel says
what each reference is read as.

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
  through the bookmarks the left panel's Quick Navigation shows. A
  bookmark belongs to the group whose reference holds its
  chromosome; Quick Navigation shows those of **This group** (with
  those of every group) or of **All** groups, and going to a
  bookmark of another group switches to that group first.
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

The **Tracks** tab of the left panel lists the tracks of the
active group. Each row has:

- a **drag handle**: drag a row to reorder the tracks; a line
  shows where the track will land;
- a **selection checkbox** that selects the track (an analysis
  input, an overlay source, a track the toolbar acts on);
- a **visibility** switch;
- a **settings** button: the options of the track's type (an
  alignment track's reads, read layout, marks and strips; a
  signal track's style, value axis and *Show negative*; a variant
  track's display and filters; an interaction track's display and
  filters, *Min score* and *Min distance* among them; and every
  track's colours, height and legend);
- a **remove** button.

A press on a track's name in the viewport selects that track
alone, and with `Ctrl` (Command on macOS) adds it to the selection
or takes it out; the panel's checkboxes and the viewport show the
same selection. The toolbar's up and down buttons and its *Height*
act on the selected tracks. A new gene, feature or sequence track
opens at 120, 73 or 112 pixels: the gene track at 120 so that a
transcriptome's Gene Detail shows without a scrollbar, the others
at the least height at which their legend fits; a feature track's
boxes are 18 pixels high. Settings > Track Styles sets each type's
heights; a settings file that holds an earlier version's built-in
heights reads these, and heights you set are kept.

Every quantitative track (coverage, signal, an alignment track's
coverage strip, the GC curve, Sashimi profiles, overlays, the read
aggregate tracks) has one **value axis**: its scale (linear, log2,
log10, square root or asinh) and *Auto*, which fits the axis to
the values in view, or a bottom and top you set.

### Tracks made from others

- **Read aggregate tracks**: an alignment track's settings and its
  read menu add a modification density track (base modifications
  from the MM and ML tags), a poly(A) tail track (Dorado's tail
  lengths) or a variant summary (the reads' bases against the
  reference) over its BAM, just below it. The alignment track's
  modification, poly(A) and mutation strips are compact views of
  the same three. A view wider than a track's *Count up to* (5 Mb
  for a variant summary or the mutation strip, 2 Mb for the
  others) is not counted, and the track says to zoom in. A variant
  summary's *Min alt reads a strand* judges a site only where its
  reference base has that many reads on each strand, so reads that
  all lie on one strand, as direct RNA reads do, lose no site.
- **Sashimi tracks**: *Add Sashimi track* (in an alignment
  track's settings or its read menu) draws the depth of the reads
  in view and an arc for each splice junction.
- **Overlay tracks**: tick two or more signal, coverage or
  alignment tracks of a group and press *Overlay*: each is drawn
  in one lane in its own colour.
- **The calls matrix**: an alignment track's Display > *Calls
  matrix* draws a row for each read and a column for each
  modified site in view.
- **The Matrix display**: an interaction track's Display >
  *Matrix* draws its contacts binned and balanced, each pair of
  bins a square above the axis.

### Subsampling badge

When an alignment track holds fewer reads than the view has (its
*Max reads* cap, 500 by default), a badge in the track's label
column shows `kept/total` (for example `500/3.2k`), on screen and
in the SVG export. Raise the cap in the track's settings (Reads)
or with `vx_set_alignment_options(name=..., max_reads=...)`; the
view then loads again.

---

## 5. Active mode

Press `Ctrl+I` (or turn on the *Active* switch in the header bar)
to enter Active Mode:

- **Hover** highlights an element and shows its details; over a
  coverage strip, a signal, a GC curve or an aggregate track a dot
  shows the value under the pointer.
- **Click** selects it; `Ctrl`+click (Command+click on macOS) adds to the selection.
- **Right-click** on a read or a modification mark shows its
  information; on a selected read it opens the read's menu (copy
  the CIGAR, the name or the sequence, other alignments, aggregate
  tracks, a Sashimi track). A right click on a base of an
  alignment track off the reads offers to group or sort the reads
  by the base or the modification call there. On a gene or a
  feature, the menu offers its Known Features tab.
- **Drag** makes a region with its statistics (mean, minimum,
  maximum, sum); `Shift`+click places a coordinate cursor and
  `Shift`+drag defines a region.

The information popup has **Copy** and **Save TSV** buttons.

---

## 6. Magnifier popup

Hold `Alt` and hover the viewport. A rounded magnified inset
opens at the cursor (1.5× to 10×, default 3×). While `Alt` is
held, `+` (or `=`) and `-` change the magnification, as does
`Alt`+scroll. Press `Alt` twice quickly (each press within 0.4 s
of the last, nothing else pressed, clicked or scrolled meanwhile)
to keep the magnifier on without holding `Alt`; twice again lets
it go. Settings > Output > Viewport sets it up.

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
group with its reference mode, its tracks and their settings, the
tracks made by analyses with their result files, the bookmarks
with their groups, each group's edit log and the open Known
Features tabs. `Ctrl+S` saves; `Ctrl+Shift+O` loads; Settings >
Startup can load the last session at start. Session files are JSON
(`.vxs`). Track data is not in the file: each track is loaded
again from its file by its path, so a session can be shared with
the data it names; when a file is missing, VX offers to skip it or
to locate it.

---

## 9. Snapshots and video

- **Snapshot**: `Ctrl+Shift+E` exports the viewport as PNG, JPEG
  or TIFF at the scale set in Settings > Output > Capture;
  `Ctrl+Shift+V` exports it as SVG.
- **Video recording**: `Ctrl+Shift+R` starts and stops it. Choose
  MP4 (H.264), WebM (VP9) or GIF, the frame rate and the capture
  mode (timer: a fixed frame rate; render: every frame drawn) in
  Settings > Output > Capture. Requires `ffmpeg` on `PATH`.
- The circular view and the dot plot export their picture as SVG
  or PNG (section 11).

---

## 10. Analysis framework

Tick the analysis selection checkboxes on the tracks you want as
inputs, then click **Analyse**. The popover lists the analyses
those tracks can take (for example, Feature Counts appears when
an alignment track and a gene track are among them); the run
dialog chooses where the analysis runs (the view, the chromosome
in view, or every chromosome of its inputs). An analysis that
needs a value with no default (Motif Search's motif) has a field
under its entry; Differential Expression first asks for its two
conditions; Modification Sites, Modification Co-occurrence and
Poly(A) Statistics offer a control or a second BAM of the group.

On a group whose reference is read as a transcriptome, the dialog
leaves out the eight analyses meant for a genome (Splice
Junctions, CNV Segmentation, Strand Bias, Simple Peak Calling,
Enrichment Over Input, TAD Boundary Detection, Contact Matrix and
Contact Frequency vs Distance), so *Run All Applicable* runs none
of them, and a line under the list says how many are left out and
why; setting the group's *Reference mode* to *Genome* offers them
again. An analysis that needs the reference (GC Content,
Nucleotide Frequency, CpG Density, Motif Search, Repeat Density,
Mismatch Rate, Coding Impact and ORF Prediction) is not offered in
a group without one.

Simple Peak Calling, Feature Prominence, Coverage Anomalies and
Variant Density Hotspots take their background from the whole
chromosome of a view or a region and list what meets it, each
whole, so a view shows the peaks the chromosome has there (and
costs what its chromosome costs). At genome scope Feature
Prominence and Coverage Anomalies take their one cut-off without
the mitochondrion's and the plastid's sequences, unless no other
sequence has a value; those sequences are still listed.

Each result is a file in the results directory (Settings > Paths;
`Results` beside the program by default, on macOS in
`~/Library/Application Support/VX/`): BED, BED12, bedGraph, TSV,
bedMethyl or BEDPE, with a manifest beside it that records the
inputs, the parameters as applied and the region. A track result
is also added as a track (Settings > Analysis), right below its
input track; a result track with nothing in view says where its
records are.

Analyses run in the background; the status bar shows their
progress: a click on a running analysis cancels it, a click on a
finished one opens its file, and a right click offers its details.

The 59 analyses span signal math, sequence analysis (ORF
prediction among them), quantification (RPKM/TPM/CPM, differential
expression, transcript quantification), splice junctions, interval
operations, variant analysis, alignment statistics, base
modifications and poly(A) tails, peak detection and copy number,
interaction analysis (contact matrices among them), and
cross-track correlation. The popover's text labels and tooltips
are the canonical short descriptions.

---

## 11. Circular view and dot plot

- **Circular view**: the toolbar's circular view button, or
  "Circular view of <sequence>" in the overview's right-click menu,
  opens a sequence of up to 20,000,000 bases (a mitochondrion, a
  plastid, a plasmid, a bacterial chromosome) as a circle in a
  window of its own, with a ring for each track of the group and
  chords for reads in pieces (back-splices, deletions, inversions).
  A drag along the circle shows that region in the linear view.
- **Dot plot**: the toolbar's dot plot button, or "Dot plot of this
  region" in the right-click menu, plots a region against itself,
  against another region, or a transcript against its gene's
  region, by exact matches of a word of 4 to 31 bases.

---

## 12. Edit mode

The **Edit** tab of the left panel edits the active group's
reference and its annotation: add, move, resize, delete or rename
genes, transcripts, exons and features, set a gene's strand or
biotype, and insert, delete or replace bases. Choose an operation,
fill its fields (*Fill from selection* takes the item selected in
the viewport; positions are 1-based, as the ruler shows them) and
press *Apply*. With the tab shown, a drag of a gene, transcript,
exon or feature moves it and a drag of its edge resizes it. A gene
whose ID other genes share (Liftoff's copies) is edited copy by
copy: a drag edits the copy dragged, and the *Gene start* field
(1-based), filled from a selected copy, tells copies on one
sequence apart.

After an edit of the bases every later coordinate moves on the
tracks VX holds in memory; a track read from its file on demand
(BAM alignments, BigWig, an annotation above 50 MiB) is drawn only
up to the first position an edit moved. The log lists every edit
with *Undo*, *Redo* and *Discard all*; *Write* saves the edited
reference (FASTA and `.fai`), annotation (GTF or GFF3 with its
gene index; in a GFF3 each copy of a gene ID gets an ID of its
own, such as `gene:ATCG00150@ChrC` or, for copies on one
chromosome, `gene:ATMG01360@Chr2:3591778`) and features (BED).

---

## 13. Known Features

With Active Mode on, select a gene (or a transcript, an exon, or a
feature named by an identifier) and right-click it; with Active
Mode off, right-click it. *Show Known Features* opens a tab in the
pane at the right of the window, which shows what public services
say about it: its name, description and place (Ensembl), the
protein (UniProt), the gene's summary (NCBI Gene), interaction
partners (STRING, and IntAct when turned on) and the backbone of
a PDB structure. Settings > Known Features turns each service on
or off, sets the species of a gene's name and the days an answer
is kept, and *Use the cache only* sends no request at all.

---

## 14. Driving VX from an AI agent

The embedded HTTP API on `127.0.0.1:9876` lets agents (e.g.
Claude via the [VX MCP server](../mcp/README.md)) drive VX
programmatically: navigate, load files, run analyses and read
their result files, capture images, edit, record video. See
[`../api/`](../api/) and [`../mcp/`](../mcp/) for the full spec.

---

## 15. Settings

Settings (`Ctrl+,`) has 14 tabs. Settings > Hotkeys rebinds the
shortcuts. Settings > Appearance > Display covers the interface
and font scale, dark mode, the grid, the labels and Active Mode.
Settings > Paths sets the reference, results, sessions and tracks
directories and the reference mode a newly loaded reference starts
in, and shows this run's log file. Settings > Analysis holds every
analysis's defaults, and Settings > Track Styles each track type's
(Value Scales among them). Settings > Known Features sets the
Known Features pane's services. Settings > Privacy holds the
optional anonymous usage statistics (off by default).

The configuration file is `vx.cfg` (INI format), next to the
executable; on macOS it is in `~/Library/Application Support/VX/`.
