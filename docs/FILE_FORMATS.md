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
| **GTF / GFF / GFF3** | `.gtf`, `.gff`, `.gff3`, plain or gzipped | Gene | Ensembl and GENCODE annotations with exon, CDS (the translon, which holds the stop codon a GTF gives on its stop_codon lines) and UTR structure; RefSeq GFF3 (NCBI's `gene-` and `rna-` prefixes, partial marks) is read as Ensembl's. A file over 50 MiB is read through a gene index saved beside it (`.gidx`). A file that holds no gene (repeat copies, peaks) loads as a Feature track, each feature with its type and attributes in its popup. Since 0.11.0 a gene is its ID on one chromosome (see *Format quirks*). |
| **BAM** | `.bam` | Alignment | A `.bai` index beside it (`reads.bam.bai` or `reads.bai`) lets VX read a region directly; make one with `samtools index reads.bam`. A file named `.bam` that is not BGZF-compressed, or that does not end with BGZF's end-of-file block (a file cut short), is refused with the reason. Base modifications (MM and ML tags), poly(A) tail lengths (`pt`) and INDEGRA's tags are read; the read aggregate, Sashimi and calls matrix views are drawn from the BAM. |
| **SAM** | `.sam` | Coverage | Read as a coverage track: each mapped record counted over its aligned bases (an intron's N not counted). For reads drawn one by one, make a BAM: `samtools sort -o reads.bam reads.sam` and `samtools index reads.bam`. |
| **BED** | `.bed`, plain or gzipped | Feature | BED3, BED6 and BED12. A feature's own colour (itemRgb) is kept. Since 0.11.0 a BED12 line's blocks are drawn as blocks joined by a line, like a spliced transcript, when they follow the format's rules (the first block at the feature's start, the last ending at its end, in order, none inside another). |
| **BigBed** | `.bigbed`, `.bb` | Feature | Self-indexed binary BED. Since 0.11.0 the records of a bed12 or bed12+N file are drawn as their blocks. |
| **bedGraph** | `.bedgraph`, plain or gzipped | Signal | Continuous signal as (chromosome, start, end, value) rows. |
| **Wiggle** | `.wig`, plain or gzipped | Signal | fixedStep and variableStep both handled. |
| **BigWig** | `.bigwig`, `.bw` | Signal | Self-indexed binary; drawn from windows read on demand at the file's own zoom levels; the recommended format for large signal data. |
| **VCF** | `.vcf`, plain, gzip or BGZF (`.vcf.gz`) | Variant | Each alternate allele of a record is shown on its own; the records keep their INFO fields, genotype columns and header lines, which Export Track Data writes back. |
| **BEDPE** | `.bedpe` | Interaction | Paired genomic intervals for chromatin contacts (Hi-C loops and the like). An anchor written end first is read swapped, and the log counts such anchors. |
| **INDEGRA process table** | `{sample}_process.txt` (`.txt`, `.tsv`) | Transcript DTI | INDEGRA's per-transcript table, recognised by its header line. |
| **VX session** | `.vxs` | (a session) | Restores the session: Load Session, `--load session.vxs`, or the API's `load_session`. |

VX does not read CRAM or BCF: convert them first
(`samtools view -b` makes a BAM, `bcftools view` a VCF). A
`.cool`, `.mcool` or `.hic` contact file is refused with the
reason: write its contacts as BEDPE (`cooler dump --join` does it
for a cooler file) and load that.

---

## Output formats

| Format | Extension | Where it comes from |
|---|---|---|
| **BED** | `.bed` | Peak calling, interval operations, gap detection and the other analyses that list intervals; an alignment track's loaded reads (Save selected track(s)); the Edit mode's features (a feature with blocks as a BED12 line). |
| **BED12** | `.bed` | ORF Prediction's ORFs, each with its blocks. |
| **bedMethyl** | `.bed` | Modification Sites, and a modification density track's rows (Save rows, `aggregate_rows`): modkit's 18 columns, every site with a modified or unmodified call. |
| **BEDPE** | `.bedpe` | Modification Co-occurrence: the pairs of sites modified together, loaded as an interaction track. |
| **bedGraph** | `.bedgraph` | Signal analyses (GC content, Z-score, signal difference and others); a signal track's data (Export Track Data). |
| **TSV** | `.tsv` | Quantification (RPKM, TPM, CPM, feature counts, transcript quantification, differential expression), splice junctions (STAR's SJ.out.tab columns with a header), gene body coverage, CNV segments, contact matrices, modification sites, poly(A) statistics, co-occurrence, variant tables, alignment statistics; a gene track's data (one row per gene, eight columns); a read aggregate track's rows (Save rows, `aggregate_rows`). Since 0.11.0 the tables of Differential Expression, Transcript Quantification, Gene Body Coverage (its transcripts), Poly(A) Statistics (on a genome) and ORF Prediction give each row's place (chrom, start 0-based, end) after its ids, as Feature Counts, RPKM, TPM, CPM and Per-Exon Coverage do, which tells a gene's copies apart. |
| **VCF** | `.vcf` | A variant track's data (Export Track Data): every ALT, INFO field and genotype column, under the file's own header lines. |
| **Manifest** | `.manifest.json` | Beside every analysis result: the analysis, the VX version, the time, each input file with its size, modification time and SHA-256 (up to a size set in Settings), the parameters as applied, the scope and region, each output file with its size and SHA-256. |
| **PNG** | `.png` | Viewport snapshot; through the API also the whole window and a single track; the circular view and the dot plot. |
| **JPEG** | `.jpg`, `.jpeg` | Viewport snapshot. |
| **TIFF** | `.tiff`, `.tif` | Viewport snapshot. |
| **SVG** | `.svg` | The viewport as editable vector graphics; the circular view and the dot plot. |
| **MP4** | `.mp4` | Video recording (H.264). |
| **WebM** | `.webm` | Video recording (VP9). |
| **GIF** | `.gif` | Video recording (animated). |
| **FASTA** | `.fa` | The view's sequence (export_region); the Edit mode's edited reference, with its `.fai`. |
| **GFF** | `.gff` | The view's genes and features (export_region). |
| **GTF / GFF3** | `.gtf`, `.gff3` | The Edit mode's edited annotation, with its gene index (`.gidx`); each loads back into VX as written. In a GFF3 each copy of a gene ID, and each of its transcripts, gets an ID of its own: `gene:ATCG00150@ChrC`, and for copies on one chromosome also the copy's first base, `gene:ATMG01360@Chr2:3591778`. |
| **Markdown / JSON** | `.md`, `.json` | A Known Features tab (Save as Markdown, Export JSON, `export_known_features`). |
| **VXS** | `.vxs` | Session file (JSON): the view, the display settings, every group's reference mode, tracks with their settings and files, and edit log, the result tracks, the bookmarks with their groups, the open Known Features tabs. The data stay in their files. |

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
  on; an index of an older format is rebuilt once (0.11.0 rebuilds
  the indexes earlier versions wrote).
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
  `transcript_id` (GTF) or `ID` and `Parent` (GFF3); a line
  without `gene_id` takes gffread's `geneID` (a `gene:` or `gene-`
  prefix dropped), so FlyBase's GFF3 as gffread writes it groups
  its mRNAs into their FBgn genes. A gene's name is its
  `gene_name`, else its `Name`, else its ID. A line whose
  attributes are split across tab fields is still read, and one
  line in the log counts such lines; records that belong to no
  gene are counted in the log too, as they are not drawn.
  Since 0.11.0 a gene is its ID on one chromosome: a `gene_id` on
  two chromosomes is two genes, and a gene line repeated on one
  chromosome that overlaps no gene line of its ID there begins a
  gene of its own (Liftoff's copies; gene lines that overlap are
  one gene). Files and tables keep the annotation's names; the
  screens (labels, popups, searches) show such a gene with its
  chromosome in brackets ("ATCG00150 (ChrC)"), or, for a copy
  beside another on its chromosome, with its chromosome and first
  base ("ATMG01360 (Chr2:3,591,778)"). A GFF3 Parent of several
  values is read value by value, and a value that names no gene or
  transcript of the file (a protein's ID) is left out and counted
  in one line of the log. A transcript line with no `gene_id`,
  `geneID` or Parent belongs to the gene its exons make, and
  without exons to none. A transposon's fragments (lines whose
  Parent names a transposable_element, transposon,
  retrotransposon, LTR_retrotransposon, non_LTR_retrotransposon,
  LINE_element, SINE_element, DNA_transposon,
  terminal_inverted_repeat_element, MITE, helitron or
  insertion_sequence, or a type ending in _transposon or
  _retrotransposon) make a gene of the transposon's ID spanning
  its line, so a GFF3 of transposons and their fragments loads as
  a gene track; a transposon without fragments is no gene.
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
