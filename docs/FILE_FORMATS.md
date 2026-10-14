# VX: File Formats

VX is read-mostly. It recognises an input by its extension and
creates the matching track type. This document lists every
supported format, the track type it maps to, and the output
formats VX writes.

---

## Input formats

| Format | Extensions | Track type | Notes |
|---|---|---|---|
| **FASTA** | `.fa`, `.fasta`, `.fna`, `.fas`, plain or gzipped (`.gz`) | Sequence | Reference genome; each reference you open creates a new group. A sequence line with a blank before a base is refused, with its line number. |
| **GTF / GFF / GFF3** | `.gtf`, `.gff`, `.gff3`, plain or gzipped | Gene | Ensembl and GENCODE annotations with exon, CDS (the translon, which holds the stop codon a GTF gives on its stop_codon lines) and UTR structure; RefSeq GFF3 (NCBI's `gene-` and `rna-` prefixes, partial marks) is read as Ensembl's. A file over 50 MiB is read through a gene index saved beside it (`.gidx`). A file that holds no gene (repeat copies, peaks) loads as a Feature track, each feature with its type and attributes in its popup. |
| **BAM** | `.bam` | Alignment | A `.bai` index beside it (`reads.bam.bai` or `reads.bai`) lets VX read a region directly; make one with `samtools index reads.bam`. A file named `.bam` that is not BGZF-compressed, or that does not end with BGZF's end-of-file block (a file cut short), is refused with the reason. |
| **SAM** | `.sam` | Coverage | Read as a coverage track: each mapped record counted over its aligned bases (an intron's N not counted). For reads drawn one by one, make a BAM: `samtools sort -o reads.bam reads.sam` and `samtools index reads.bam`. |
| **BED** | `.bed`, plain or gzipped | Feature | BED3, BED6 and BED12 (blocks). A feature's own colour (itemRgb) is kept. |
| **BigBed** | `.bigbed`, `.bb` | Feature | Self-indexed binary BED. |
| **bedGraph** | `.bedgraph`, plain or gzipped | Signal | Continuous signal as (chromosome, start, end, value) rows. |
| **Wiggle** | `.wig`, plain or gzipped | Signal | fixedStep and variableStep both handled. |
| **BigWig** | `.bigwig`, `.bw` | Signal | Self-indexed binary; drawn from windows read on demand at the file's own zoom levels; the recommended format for large signal data. |
| **VCF** | `.vcf`, plain, gzip or BGZF (`.vcf.gz`) | Variant | Each alternate allele of a record is shown on its own; the records keep their INFO fields, genotype columns and header lines, which Export Track Data writes back. |
| **BEDPE** | `.bedpe` | Interaction | Paired genomic intervals for chromatin contacts (Hi-C loops and the like). An anchor written end first is read swapped, and the log counts such anchors. |
| **INDEGRA process table** | `{sample}_process.txt` (`.txt`, `.tsv`) | Transcript DTI | INDEGRA's per-transcript table, recognised by its header line. |
| **VX session** | `.vxs` | (a session) | Restores the session: Load Session, `--load session.vxs`, or the API's `load_session`. |

VX does not read CRAM or BCF: convert them first
(`samtools view -b` makes a BAM, `bcftools view` a VCF).

---

## Output formats

| Format | Extension | Where it comes from |
|---|---|---|
| **BED** | `.bed` | Peak calling, interval operations, gap detection and the other analyses that list intervals; an alignment track's loaded reads (Save selected track(s)). |
| **bedGraph** | `.bedgraph` | Signal analyses (GC content, Z-score, signal difference and others); a signal track's data (Export Track Data). |
| **TSV** | `.tsv` | Quantification (RPKM, TPM, CPM, feature counts), variant tables, alignment statistics; a gene track's data (one row per gene, eight columns). |
| **VCF** | `.vcf` | A variant track's data (Export Track Data): every ALT, INFO field and genotype column, under the file's own header lines. |
| **Manifest** | `.manifest.json` | Beside every analysis result: the analysis, the VX version, the time, each input file with its size, modification time and SHA-256 (up to a size set in Settings), the parameters as applied, the scope and region, each output file with its size and SHA-256. |
| **PNG** | `.png` | Viewport snapshot; through the API also the whole window and a single track. |
| **JPEG** | `.jpg`, `.jpeg` | Viewport snapshot. |
| **TIFF** | `.tiff`, `.tif` | Viewport snapshot. |
| **SVG** | `.svg` | The viewport as editable vector graphics. |
| **MP4** | `.mp4` | Video recording (H.264). |
| **WebM** | `.webm` | Video recording (VP9). |
| **GIF** | `.gif` | Video recording (animated). |
| **FASTA** | `.fa` | The view's sequence (export_region). |
| **GFF** | `.gff` | The view's genes and features (export_region). |
| **VXS** | `.vxs` | Session file (JSON): the view, the display settings, every group's tracks with their settings and files, the result tracks, the bookmarks. The data stay in their files. |

---

## Chromosome naming

VX matches chromosome names between files that follow different
conventions:

| Convention | Example | Typical sources |
|---|---|---|
| UCSC | `chr1`, `chrX`, `chrM` | GRCh38 FASTA from UCSC, many BAM headers |
| Ensembl | `1`, `X`, `MT` | Ensembl GTF annotations |
| NCBI / RefSeq | `NC_000001.11` | RefSeq assemblies |
| UCSC scaffolds | `chrUn_KI270742v1`, `chr11_KI270721v1_random`, `chr1_KI270762v1_alt` | UCSC's GRCh38 FASTA, ENCODE BAMs |
| GenBank / Ensembl scaffolds | `KI270742.1`, `GL000195.1` | Ensembl GTF annotations, GENCODE's FASTA |

So when you open a BAM that calls it `chr1` and a GTF that calls
it `1`, they line up. A scaffold is matched by its accession and
version between these forms (`KI270721.1` is
`chr11_KI270721v1_random`), so a different version matches
nothing; where two names carry one accession, neither is used and
the log says why.

---

## Indexing

- **BAM**: a `.bai` beside the file gives VX direct access to a
  region. Make it with `samtools index your.bam`.
- **VCF**: read whole when it is opened; no `.tbi` is needed.
- **GTF / GFF over 50 MiB**: VX writes a gene index beside the
  file (`.gidx`) at the first load and reads through it from then
  on; an index of an older format is rebuilt once.
- **BigBed / BigWig** are self-indexed: no sidecar needed.

---

## Compression

- gzip (`.gz`, including BGZF, what `bgzip` writes) is read for
  FASTA, GTF, GFF, BED, bedGraph, Wiggle and VCF files. For all
  but FASTA, every gzip member is read, and a BGZF file must end
  with BGZF's end-of-file block or it is refused as cut short.
- BAM, BigBed and BigWig are compressed binary formats and are
  handled natively.

---

## Format quirks worth knowing

- **GTF / GFF**: genes are built from `gene_id` and
  `transcript_id` (GTF) or `ID` and `Parent` (GFF3). A gene's
  name is its `gene_name`, else its `Name`, else its ID. A line
  whose attributes are split across tab fields is still read, and
  one line in the log counts such lines; records that belong to
  no gene are counted in the log too, as they are not drawn.
- **BAM**: subsampling applies when the view holds more reads
  than the track's *Max reads* (default 500). The badge in the
  track's label column (`kept/total`) tells you when this is
  active. Raise the cap in the track's settings.
- **VCF**: an alternate allele is reduced to the bases it changes
  and drawn there, with its own frequency (AF, else AC over AN).
  An entry that states no variant (`.`, `*`, a gVCF's `<*>` or
  `<NON_REF>`, or REF itself) is not drawn; the track's label
  counts such entries. A symbolic allele (`<DEL>`, `<DUP>`, ...)
  is drawn from POS to its END (else its SVLEN).
- **BigWig**: zoom levels are precomputed in the file; VX picks
  the level whose bins are at or below the bases per pixel.
  Analyses and exports read the whole file.
