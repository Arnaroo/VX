# VX Genome Viewer — File Formats

VX is read-mostly. It auto-detects input by extension and creates
the appropriate track type. This document lists every supported
format, the track type it maps to, and the output formats VX
writes.

---

## Input formats

| Format | Extensions | Track type | Notes |
|---|---|---|---|
| **FASTA** | `.fa`, `.fasta`, `.fna`, `.fa.gz` | Sequence | Reference genome; the first FASTA you open creates a new group. Gzipped FASTA is supported transparently. |
| **GTF** | `.gtf` | Gene | Ensembl / GENCODE format with `gene_id`, `transcript_id`, `exon_number` attributes. Full exon / CDS / UTR structure. |
| **GFF / GFF3** | `.gff`, `.gff3` | Gene | Generic Feature Format v3. Same downstream rendering as GTF. |
| **BAM** | `.bam` | Alignment | Requires a `.bai` index next to the BAM (auto-located). Indexed range queries; reads stream in by region. |
| **SAM** | `.sam` | Alignment | Whole-file read. Use BAM for large files. |
| **BED** | `.bed` | Feature | BED3, BED6, and BED12 (transcript) variants. |
| **BigBed** | `.bigbed`, `.bb` | Feature | Self-indexed binary BED. |
| **BedGraph** | `.bedgraph`, `.bg` | Signal | Continuous signal with explicit (chr, start, end, value) rows. |
| **Wiggle** | `.wig` | Signal | fixedStep and variableStep both handled. |
| **BigWig** | `.bigwig`, `.bw` | Signal | Self-indexed binary; the recommended format for large signal data. |
| **VCF** | `.vcf`, `.vcf.gz` | Variant | Variant calls with quality, genotypes, and INFO annotations. Index `.tbi` is auto-located if present. |
| **BCF** | `.bcf` | Variant | Binary VCF. |
| **BEDPE** | `.bedpe` | Interaction | Paired genomic intervals for chromatin contacts. |

---

## Output formats

| Format | Extension | Where it comes from |
|---|---|---|
| **BED** | `.bed` | Peak calling, interval operations, gap detection, generic interval analyses. |
| **BedGraph** | `.bedgraph` | Signal analyses (GC content, Z-score, signal difference, peak prominence). |
| **TSV** | `.tsv` | Quantification (RPKM, TPM, CPM, feature counts), variant tables, alignment statistics. |
| **PNG** | `.png` | Viewport snapshot. |
| **JPEG** | `.jpg`, `.jpeg` | Viewport snapshot. |
| **TIFF** | `.tiff` | Viewport snapshot. |
| **SVG** | `.svg` | Vector viewport export (one-shot, full-resolution). |
| **MP4** | `.mp4` | Video recording (H.264). |
| **WebM** | `.webm` | Video recording (VP9). |
| **GIF** | `.gif` | Video recording (animated). |
| **FASTA** | `.fa` | Sequence region export. |
| **VXS** | `.vxs` | Session file (JSON-based; round-trips all open files, viewport, track layout, bookmarks). |

---

## Chromosome naming

VX resolves the three common chromosome-naming conventions
automatically:

| Convention | Example | Typical sources |
|---|---|---|
| UCSC | `chr1`, `chrX`, `chrM` | GRCh38 FASTA from UCSC, many BAM headers |
| Ensembl | `1`, `X`, `MT` | Ensembl GTF annotations |
| NCBI / RefSeq | `NC_000001.11` | RefSeq assemblies |

The internal `ChromosomeAliasResolver` lets you mix files using
different conventions in the same group — when you open a BAM
that calls it `chr1` and a GTF that calls it `1`, they line up
correctly.

---

## Indexing

VX is sensitive to indexes:

- **BAM** requires `.bai` for the seekable random-access used by
  the async region fetcher. If you only have `.bam`, generate the
  index with `samtools index your.bam`.
- **VCF** uses `.tbi` if present (much faster); otherwise it falls
  back to a full-file scan.
- **BigBed / BigWig** are self-indexed — no sidecar needed.

---

## Compression

- `.gz` is supported for FASTA, GTF, GFF, BED, and VCF (where the
  format spec allows).
- BAM/BCF/BigBed/BigWig are inherently compressed binary
  formats and are handled natively.

---

## Format quirks worth knowing

- **GTF / GFF**: VX expects `transcript_id` and `gene_id`
  attributes on exon / CDS / UTR records. Files missing
  `transcript_id` will still load but exons won't be grouped
  into transcripts.
- **BAM**: subsampling kicks in when the visible window contains
  more than `max_reads` reads (default 500). The badge in the
  top-right of the alignment track tells you when this is
  active. Raise the cap via the track options popover.
- **VCF**: per-variant `INFO`/`FORMAT` fields are not normalised;
  what's displayed in Active Mode is what the VCF says.
- **BigWig**: zoom levels are precomputed in the file; VX picks
  the best zoom for the current viewport automatically.
