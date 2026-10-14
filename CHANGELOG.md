# Changelog

User-visible changes to VX. Newer entries are at the
top.

Detailed development history is maintained in private trackers;
this public changelog focuses on what changed in the binaries and
APIs between public releases.

---

## v0.10.0 "Banksia": 2026-10-14

### Annotations

- The features of an annotation file that holds no gene are drawn in a lighter blue of the same hue on the dark scheme, 3.4 to 1 against its background where they were 2.4 to 1, with their names in black; the light scheme's steel blue is unchanged, and the legend shows their colour where it showed grey
- Such a track has a Feature colour button in the track panel; a colour set there is kept on both schemes and in a session, and Reset to Global Defaults gives the scheme's colour back
- A GTF or GFF3 file that holds no gene (no record with a gene_id, a Parent or a gene line, such as a file of ATHILA retrotransposon copies) loads as a feature track, each feature drawn with its type and its attributes in its popup; it loaded as a gene track without a gene, which drew nothing at any zoom
- In a file with genes, the records that belong to no gene are counted in one line of the log, as they are not drawn; they were dropped without a word
- A GTF or GFF3 file below 50 MiB loads with its genes. Every such file made an empty gene track, drawn with nothing in it and empty to every analysis and to get_genes; a larger file, read through an index, was not affected
- A transcript that begins at the first base of its sequence is kept, with its exons, and a gene whose line begins there keeps its start (a start at the first base was read as no position: the transcript was dropped and the gene moved to its first transcript's start)
- A BED's features without a colour of their own (no itemRgb), and an analysis's features, are drawn in the scheme's annotation colour (steel blue, a lighter blue on the dark scheme) with their names in the ink that reads on it; they were black on both schemes, 1.3 to 1 against the dark background. A feature's itemRgb is kept
- Every feature track (a BED's, a BigBed's, an analysis's) has the Feature colour button in the track panel; a colour set there is drawn for every feature of the track on both schemes, its names in the ink that reads on it

### SVG export

- A picture exported in the dark scheme has the dark background, ruler and labels; it had the light ones, with only the loops, variants and modifications in their dark colours

### Coverage navigation

- The previous and next coverage buttons and next_coverage_region scan beside the window, which keeps drawing and taking input; the pressed button shows an ellipsis until the scan ends, and a second scan is refused until the first has ended
- The previous and next coverage buttons can be pressed with a BAM, a bedGraph or a BigWig loaded and no coverage track; they stayed greyed out
- The left panel's previous and next coverage buttons and the API's next_coverage_region read the coverage of a BAM, a coverage track, a bedGraph or a BigWig at every base, name the track they read, and say when no track has coverage; they read a coverage track alone, at every twentieth of the view, and answered a missing one as no region
- A running coverage scan can be stopped, with the pressed « or » button, which shows a stop sign half a second after the press, or through the API's cancel_coverage_scan, and a new scan can start at once; a scan ran to the end of the chromosome (a minute or more on a large BAM) and every scan asked meanwhile was refused
- A scan that reads nothing for 60 s is stopped, says so in the status line, and next_coverage_region answers it STALLED (HTTP 504); a read that never returned left every later scan refused until VX was restarted

### API

- next_coverage_region answers when its scan ends, however long it takes, with the scan's time in scanSeconds, and a call while a scan runs is answered BUSY; a scan longer than 30 s was answered TIMEOUT while the window went on scanning, and the late answers then went to the requests that followed
- The state given to external tools lists, for each signal track, the window held: its chromosome, bounds, zoom level or raw, and the number of stretches
- export_image writes the viewport to a PNG, JPEG or TIFF file at a chosen scale, as the Snapshot button does
- set_variant_options refuses a mode it does not have and a switch that is not true or false, by name, and takes show_other; an unknown mode fell to the default and "true" as a string turned a switch off
- /state and the answer of set_interaction_options give each loops track's opacity as drawn and whether the user set it (interaction.opacity, interaction.customOpacity); neither was reported
- Each request gets its own answer; a request the window does not answer in time is answered TIMEOUT and its late answer is dropped and named in the log, where it went to whichever request was waiting when it came, so that a get_state could receive an export's answer and each answer after it could be one request late
- The TIMEOUT answer says how long the window was given and that the request may still be carried out; it said that the dispatch timed out with a possible deadlock
- load_session in a window skips a missing input file and names it in its answer's inputs_missing, as without a window; it opened the missing-files dialog, and its answer waited for it until it timed out
- read_result_rows gives the rows of a result file an analysis wrote, up to 1000 a page, with the file's column names and the offset of the next page, and refuses any file that is not a result; the MCP tool vx_read_result_rows calls it, where an analysis answered only its counts and a path
- Shutdown ends a viewer with a window as it ends one without: the window's size is saved, the window closes and the process ends at once, and at the latest 5 s after the answer even with a dialog left open; until now a dialog left open kept the viewer running with its size not saved
- read_result_rows reads only the files the analyses wrote, in this run or in the run that saved a session it reopens (each one's output, its manifest and the files its summary names), and refuses any other path; it also read every file under the results directory and under any results_dir a run had been given, so a run given the home folder as its results_dir opened that folder to the local API

### Gene index

- Building the index of a large GTF or GFF3 reads only the attributes the index and its gene table use (the whole Ensembl human GTF in about 3 s on the test machine), the saved index the same byte for byte
- The format is GDX7 (GDX6's layout under a new magic, because the grouping and the rows changed); an index of GDX6 or earlier is rebuilt once
- The format is GDX6, which keeps each gene's row of the gene table and the count of lines whose attributes are split across tab fields; an index of GDX5 or earlier is rebuilt once (Case 1's chr19 annotation: 335,310 bytes where GDX5 took 184,022)
- An index that ended inside its second chromosome is rebuilt with each gene once; the first chromosome's genes were added twice

### Recording

- A recording's start, its stop and a change of the viewport's size during it are information lines of the log; each was counted as an error in the status bar
- The frame is the viewport's size at the start, rounded down to even, and the recording indicator keeps its width whether a recording runs or not; the indicator appeared at a recording's start and widened the toolbar
- GIF, MP4 and WebM recordings are opaque whatever the window does; a window made narrower while recording left transparent bands in a GIF

### Status bar

- The error counter keeps its place whether there is an error or not, drawn only when there is one, so the viewport keeps its height through a session; it appeared at the first error and took 11 pixels from the viewport for the rest of the session, so a session's first recording was 12 pixels taller than the next

### Sessions

- A session of the demo data restores the demo (the same at every launch) with the tracks it holds, in its order and with their settings, a TAD boundary line on the demo's loops among them, and the group that was active when it was saved is active again; such a session restored its result files alone, and one without a result file never finished restoring
- What a restore does not make (a missing file that was skipped, a track with no file) is named with its reason at the end of the restore in the status bar, in the log and in the API's state; it was left out without a word
- After a session restore, the message on reused and missing result files is shown after the view is set; the view's position wrote over it at once
- The session restored at start begins a quarter of a second after the window opens; it could wait tens of seconds while the window redrew
- On reopening a session its result files are reused, not recomputed: each that is still there is loaded as its track with its manifest's parameters, each that is missing is left out with a line in the log and the status bar (3 result files reused, 1 missing: ...), and never asked for in the missing-files dialog; the API's load_session and /state give results_reused and results_missing
- The API takes save_session and load_session; every setting the track panel changes is kept in the session and restored, where the label size and gap of every track, a gene track's isoform heights and label sizes, a coverage track's fill, a signal track's smoothing method, window function, negative colour, gradient and view scaling, a variant track's tooltips, impact floor and zygosity and impact colours, a loops track's least distance and an alignment track's density automation, fragment colours and strip height were lost between sessions
- An alignment track keeps its minimum MAPQ, fragment mode, coverage colour mode, modification options and colours, mark style, poly(A) colour, and its mate-line, splice-junction, back-splice and stripe settings
- A session saved before 0.10.0 opens its loops tracks at the scheme's opacity unless it holds an opacity other than 0.5, which stays the track's own; the stored opacity was drawn on both schemes

### Demo data

- The genome demo has its coverage track each time the demo is made, as when a session restores it; it had one only the first time in a run

### HTTP API

- set_config refuses a key it does not read, naming it and the keys it reads; it answered Configuration updated and changed nothing (interface_scale, say, for interfaceScale)
- An error answer carries its HTTP status (400, 404, 405, 409, 501, 503, 504 or 500 by its code) with the same JSON body, and the API sends no CORS headers and refuses OPTIONS; every error was sent as 200 and a page in a browser could drive the API

### Loading

- A session loads any number of files; every load after the 50th failed ('Failed to create plugin'), because each load was counted against a fixed limit that nothing lowered
- Cancel and cancel_loading work for every load of a session; after a few loads they failed with an internal error and stopped nothing, because the background loader was dropped whenever a load ended and could be remade only five times
- Cancel stops the reading of a VCF, BED, bedGraph or Wiggle file, or of a BAM's header and index, within a megabyte; it waited for that step to end
- A cancelled file load stops at its next progress step and the status bar says it was cancelled, with no dialog; after a cancel through the API the queue goes on at once with the next file, and the window's Cancel still clears the queue; the load ran to its end first and a 'Failed to load file' dialog appeared, for a cancel through the API too (cancel_loading now answers cancelled, and loading_status gives it)
- A file that fails to load through the API (load_file, load_session, load_demo) opens no dialog; the failure is in loading_status, the log and the error counter, and a file opened from the window still shows its dialog; until now an API load's failure opened the dialog in a window and nothing reached the log
- A .sam file is read as a coverage track, each mapped record counted over its aligned bases (an intron's N not counted, as VX counts a BAM's depth); it was opened as an alignment track, which reads no SAM text, and stayed empty with nothing in the log

### Bookmarks

- The left panel's bookmark buttons and the bookmark keys open a bookmark's stored region exactly, as goto_bookmark does; they opened it one base to the left, the buttons could not open a bookmark at position 0, and they kept the view's chromosome when the chromosome list wrote its name otherwise
- goto_bookmark resolves a chromosome named by an alias of the reference (1 for chr1); it took the name as written, a view of nothing
- add_bookmark without a region answers NOT_READY until a reference is loaded; on a viewer with nothing loaded it bookmarked chr1:0-10000
- add_bookmark and goto_bookmark take a region as chromosome:start-end (0-based start, end exclusive, digits alone; the chromosome is everything before the last ':') and refuse any other text, naming it; any text was accepted, and a chromosome without a usable start and end bookmarked the current view in silence
- + Bookmark Current View, a bookmark's update arrow and the add-bookmark key add nothing while no reference is loaded and say why in the status line, as add_bookmark does; once every group was removed they bookmarked chr1:0-10000, a view of nothing

### Alignment tracks

- At views wider than about 2 Mb the coverage strip holds at most four million values, each the greatest depth of its bin, so it looks as before and its readout names the bin; it held two arrays the length of the whole window (some 700 MB at a whole chr19 view)
- Every read of the view counts in the coverage strip (the view is read to 20 times Settings' BAM max records per query, 2,000,000 by default), and the reads kept are a sample of the whole view, the same at every visit; only the first 100,000 reads by position were kept and the strip was counted from them, so the right part of a deep view showed no reads and a flat coverage
- The open BAM file and its index are kept for every view a track fetches reads for, and given back when the last track of that file is removed; each fetch opened the file and read its index again
- Minimap2's tp tag of type A is read as its character, so tp:A:S and tp:A:I mark a read secondary in the display as in the export; the display read the tag as a text and saw nothing
- When a view holds more reads than the read budget (a whole chromosome of a deep BAM), the coverage strip is drawn as far as the reads were read and ends there with the line 'coverage read to 4.79M; zoom in for the rest', and the readout past that point says the depth was not read; the strip and its readout said 0 there, where reads exist, with nothing on screen to say so

### Toolbar

- After a change of interface scale the toolbar is laid out again at once, also while the view redraws without pause (with an Active Mode region selected); its rows could stay as they were

### Other

- Labels, buttons, check boxes and menu items show a path, a file, track or sequence name or any other text with its underscores; each underscore was read as a keyboard mnemonic and dropped, so ColCEN_ATHILA showed as ColCENATHILA
- macOS: the main window could stay invisible while the API answered, because GTK drew it through an OpenGL path that never reached the screen; the viewport is now drawn in VX's own OpenGL context and painted with the rest of the window
- macOS: the viewport drew its labels but none of its shapes, because its shaders were written for an OpenGL version Apple does not provide; the shaders now follow the version and profile the OpenGL context reports
- macOS: the window had no title bar and opened at the top left of the screen; it now has the system's title bar and buttons, opens centred, and Command-Q quits
- macOS: the settings, results and sessions were written inside VX.app, which broke its signature and, where the app could not be written to, lost the settings at every start; they are now kept in ~/Library/Application Support/VX
- macOS: the app carries the GTK files its dialogs need (opening a file on a Mac without Homebrew's GTK ended VX), needs no launcher, and macOS knows it as VX, with its name, icon and Retina setting
- macOS: the disk image said VX runs on macOS 13 and that a first launch is allowed with right-click and Open; it now says macOS 26, and how macOS 15 and later let it through (System Settings, Privacy & Security, Open Anyway)
- macOS: the viewport's text used the system's Menlo font instead of the bundled DejaVu Sans Mono
- loading_status: a demo case being downloaded, checked or loaded is a load in progress, with its stage and progress (and its job under demo), and one that fails or is cancelled is reported done with its error; demo_status lists the cases, their sizes and whether each is in the cache
- Exporting a region with nothing loaded answers an error and writes nothing; it answered success with a path
- load_file answers Queued with the position when the file waits behind another load; it answered Loading
- The MCP server has vx_click_element, vx_export_image and vx_set_track_scroll, encodes a track's name, and reads an error answer whatever its status
- Signal analyses (difference, ratio, Z-score, region differential, enrichment over input, prominence, anomalies, correlation, signal at features, heatmap, profile): one chromosome is held at a time and the result is written as it is made, where every chromosome of every input was held at once. A BAM with more than 500 references is read like any other: the window on screen was taken in its place, without a word. A region with no data gives an empty result: it gave the whole track
- Feature Counts counts reads. A read is counted for the one gene whose exons it meets (three ways to decide: union, intersection_strict, intersection_nonempty; an optional strand; exons or whole genes), and the answer says how many records were left out and why. It summed the read depth over each gene's whole span, introns included, and called the sum a count: a gene with 3 reads could show 155
- RPKM, TPM and CPM are computed from read counts, the length of each gene's exons and a library size that is named (the reads counted for genes, every read counted, or a number given), over the whole BAM whatever the region, so a gene has one value at any scope. They were computed from summed depth over gene spans, and at a narrower scope divided by that region's own total
- Feature Counts, RPKM, TPM and CPM take an alignment track (a BAM). A coverage or signal track is refused, with a pointer to Signal at Features and Per-Exon Coverage, which give the depth over genes and exons
- Symbolic variants (<DEL>, <DUP>, ...) reach to their END in the variant analyses; they ended one base after their start
- Links and folders (the suggestion mail, the results folder) open through GIO's default application for the URI, not through a child xdg-open, open or explorer
- Gene tracks, popups, legends, Settings and the SVG export name the annotated translated region translon where they said CDS (the legend's Translon (coding), a segment's label translon, a transcript's translon segments and regions), and the API's transcript fields cdsCount and cds are translonRegionCount and translonRegions; the file formats' own name for the feature, CDS, is read as before
- Export Track Data, a gene track over 50 MiB (read through the gene index): the table has a smaller file's eight columns (gene_id, gene_name, chrom, start, end, strand, biotype, transcript_count) with each gene's values as its model has them, in the same order, so an annotation gives one table whatever its size; it had five columns of the index's own values: no name for a gene line without gene_name (1,376 of the 3,547 genes of Case 1's chr19 annotation, where the model names the gene by its id), the span of all of a gene's lines, a row for a gene that has no model, and genes beginning at one base in no fixed order
- Feature Counts, RPKM, TPM, CPM, Per-Exon Coverage and Bin Statistics: the minimum MAPQ of Settings, Analysis applies to them as to the alignment statistics; they used 0 whatever Settings said
- Feature Counts on a region lists a gene that lies past the end of the BAM's reference, with no read, as genome scope does; it was left out
- Interval subtraction, Export Track Data and a feature track saved as BED: a feature without a score is written ".", which loads back as no score; it was written "nan"
- Feature Counts, RPKM, TPM, CPM, Per-Exon Coverage and Bin Statistics take count_qc_failed: a record that failed QC (flag 0x200) is a read and part of a BAM's depth by default, as before, and count_qc_failed=false leaves it out (the counting analyses report it as skipped_qc_failed); there was no way to leave such records out
- Analyses, saves and usage reports hand their results to the window through one main-thread call; a timer made on the worker thread could keep a stale id, print "GLib-CRITICAL: Source ID ... was not found when attempting to remove it", or lose the call
- macOS: Command+click adds to the selection, Command+Shift+drag zooms to the box drawn and Command+scroll zooms, as Ctrl does on Linux and Windows, and the Active Mode hint says Cmd; they took Control, which is the secondary click on a Mac

### Settings > Track Styles

- The default heights of the alignment and variant tracks are given to a new track, as the other types' are, and set_config trackHeight still wins for its run; they were saved and never applied, and a new alignment track was always 200 px tall

### Analyses through the API

- analysis_status says complete only once the analysis has ended, with running false and its result, output path and manifest given; while the manifest was written (its inputs checksummed, up to 1 GiB) it said complete with running still true and no result

### Result manifests

- The run's time and each input's modification time are written with the UTC offset; they had none

### Reference groups

- Removing a group frees its data (the memory of its sequence and its index's file mapping) when it is removed; the data stayed until the viewer exited

### Left panel

- At the first start the panel opens at least as wide as its controls need; it was narrower, and the controls were cut at the right

### Variant tracks

- A genotype with no allele called (./.) is its own category, 'No call', drawn in grey and named in the legend; it was drawn and counted as homozygous reference while its click text said not called
- The SVG export draws each alternate allele as the screen does (its colour, its band to END, a record's heads stacked on one stem, its bars sharing their place, the density's columns); it drew one mark per record by the record's type and first frequency
- A genotype of two different alternate alleles (1/2) has its own zygosity colour and legend entry, "Two alternates"; it was grouped with 1/1 under "Alternates only"
- Each alternate allele of a record is read, drawn and named on its own, by the rule the variant analyses read; the loader typed a record by its first ALT alone, and "." and "*" were drawn as SNPs
- An entry that states no variant (".", "*", a gVCF's <*> or <NON_REF>, or REF itself) is not drawn; the track's label counts it and the click text names it with the reason
- A symbolic allele reaches to its END (else its SVLEN) on screen, in the click text and in the export, and a deletion that starts before the view is drawn; it was one base long, and was not drawn when it started before the view
- Each allele has its own frequency, its AF or else its AC over AN, for the colour and height by frequency and for the least frequency; the first AF was kept for the whole record and AC and AN were not read
- The click text lists every alternate allele with its type, the bases it changes, its frequency and, for a symbolic allele, the bases it covers, END and SVLEN, and gives the genotype as written (1/2 read "1/1 (homozygous alternate)")
- The density display is drawn in the track's type colours and opacity and follows "Color by"; it had three colours of its own at a fixed opacity
- "Show MNPs and complex", "Min QUAL" and "Min allele freq" are in the track's settings, the legend shows the colours of "Color by", and the IDs are readable on the dark scheme; no control reached the first three, there was no legend, and the IDs were dark grey on dark grey
- A click names the record its mark was drawn for, and a VCF that names a chromosome otherwise than the reference (21 for chr21) is drawn; the first record at that position on any chromosome was named, and such a VCF showed "No variants in view"

### Intron collapse

- The position under the pointer follows the collapsed drawing; it named a base inside a collapsed intron

### Track labels

- With Scroll on, the view redraws only while a long track name moves; it redrew thirty times a second, the pauses included

### Open menu

- The menu closes before the file chooser it opens; it stayed open behind the chooser and took the next click

### Screenshots and image exports

- Every track name is drawn at rest, so two captures of one view are the same image; long names were drawn where the label animation had carried them

### First start

- The question about anonymous usage statistics blocked the main window until it was answered; it now leaves the main window usable

### Diagnostics

- When the viewport's OpenGL could not be set up nothing said why, and a shader error was followed in the log by two kilobytes of filler; the log now says why, and gives only the driver's message
- The usage statistics trace is no longer written to stderr at every start (VX_DEBUG_USAGE=1 shows it); VX_DEBUG_ALPHA=1 reports, once a second, how many pixels of the frame just drawn are not opaque; VX_GL_OPAQUE=1 asks for a viewport buffer without an alpha channel

### MCP server

- The two screenshot tools return the image as an image a model can see; they returned it as text holding the PNG's base64 data, which no MCP client shows as an image, and the server reads the viewer's address from VX_API_BASE (default http://127.0.0.1:9876)

### Demo datasets

- Open > Open Demo Dataset and the API's load_demo download one of the paper's five case studies (each under 1 GB) into the cache directory, check the zip and every file against the SHA-256 values VX holds, and load the files in order at the view of the case's figure, a case already in the cache opening without a download and a stopped download resuming where it stopped; VX had no demo data, and the paper's data were the full deposits of 10 GB and more

### Settings > Paths > Demo Data

- The address the demo zips come from, the demo-data-v1 release by default, which VX_DEMO_BASE_URL overrides, so that a mirror or a local copy can be used

### Interaction tracks

- When TAD Boundary Detection completes, its boundaries are drawn on the track it ran on (a line at each boundary's centre in the heatmap mode), kept by a session (the demo's loops track's too) and given by the API; the lines were never drawn, because nothing filled them
- A BEDPE anchor whose end is before its start is swapped as the file is loaded, and one warning in the log counts them; the track kept it as written, so the display showed it only in a window that held all of it and the heatmap drew it about four thousand million bases wide, while the analyses read it in order

### Export Track Data

- A variant track's export is named .vcf and a signal track's .bedgraph, as their contents are; every export was named .tsv
- The region asked for is applied to every kind of track (the whole BAM was written whatever was asked); alignments are written one record at a time, where every read of a chromosome was held; a kind of track the export does not write fails by name, where it reported success and wrote nothing
- Minimap2's tp:A:S and tp:A:I tags make a record secondary in the read_class column; the tag was read as text and never matched

### Demo

- The demo's sequence, coverage and signal are the same at every launch; their noise came from the clock, so two screenshots of the demo differed

### Text

- Text up to 14 pixels is drawn from a second atlas rasterised at 16 pixels times the display's scale, so small captions and legends (7 to 8 pixels) are crisper; everything was drawn from the 48 pixel atlas shrunk four to seven times, soft and grey
- Ten messages (the load's remaining time, the usage statistics dialog, the gene list of the sequence search, the copyright line) wrote an en or em dash through an escape the text check could not see; they use a colon, a comma or a hyphen, and the check reads escapes
- The window's title, its messages, dialogs, tooltips, the API's errors, the configuration file's comments and the SVG export's header use no en or em dash (the window's title; Keyboard Shortcuts: Capture; chr1:1,000-2,000; Failed to load a.bam: the reason); 50 texts had one, and a check in the unit gate keeps them out
- The About tab's changelog, the Help text and the MCP server's descriptions name no internal session, decision or register id, internal path or source file; 35 of their lines did, and a check in the unit gate keeps them out

### Lines

- An axis-aligned line is drawn on whole pixels (a 1 px line fills one row), and a region's borders stay inside the region; a 1 px line at a whole coordinate covered two rows at half strength
- A stroke is blended with its own colour. Light lines glowed two pixels wide and mid-grey lines vanished on a white background, because their smoothed edges were added to the picture at full colour
- A stroke keeps its weight on a HiDPI display and in a capture at scale 2 or 4; it was one physical pixel at any scale, a hairline beside text and boxes that do scale

### Alignments

- The class switches (unique primary, multi-primary, multi-secondary) hide reads as they load, so the rows close up; they hid reads as they were drawn and left their rows empty
- When the filters hide every read of the view the track says so ("all N reads hidden by the filters"); it was blank
- segregate_reads_by_class and group_by "class" group the reads by their colour class (unique primary, multi-mapped primary, secondary or supplementary) under labelled bands, in fragment mode too; segregate_reads_by_class grouped them by type, with secondary and supplementary apart
- The SVG export draws what the screen draws: the bands, each read's blocks and splice lines on its row, the clip, poly(A) and modification marks, the coverage and summary strips, the colour mode in force; it drew one rectangle per read on rows of its own and blank header rows
- The modification summary strip is drawn in one batch from the counts per base; it drew one rectangle per call (25,000 draw calls for 500 reads of 50 sites)
- The summary strip, the aggregator strip and the Classic dots use the one palette of the modification marks, or a colour the user set through the API or a session; they used their own red, green, blue and amber
- A read's soft and hard clips are read from the CIGAR whole (a soft clip after a leading hard clip counts), in the read popup and the back-splice detection; the first and last operations alone were read
- The coverage strip's depth-ratio colouring works: the mapped records come from the BAM index (what samtools idxstats prints), or from the first genome-wide alignment statistic; nothing set them, and the expectation divided by the view's width
- Changing the modification probability threshold recounts the modification strip; it kept the old count until the view left the loaded region
- Soft and hard clips are marked outside the read, on their own side, at every density level from full detail to coverage lines and whatever the subsampling; they were marked at the read-blocks level only (where 500 subsampled reads land), as a tint inside the read at the thin-lines level, and not at all otherwise
- A poly(A) tail (Dorado pt tag) is drawn at the read's 3' end beyond its clip marks at every density level, in Settings' "Poly-A tail" colour, with a switch in the track panel; it was drawn at the two most detailed levels only, over the clip mark, in a colour Settings could not change
- At full detail with a reference loaded, only the bases that differ from it are painted (a CIGAR = or X decides by itself, an N is grey); without a reference every base is painted and the legend says so. Every base was painted, matches too
- A colour or detection setting changed in the track panel shows at once; the reads kept their old colours until the region was loaded again
- The Row Heights of each density level set the height the rows are drawn at; they changed only the scroll extent
- The track panel has the options the README promised (max reads, subsampling, minimum MAPQ, fragments, base quality, poly(A) tails, the modification marks and the aggregators), and an option applied when reads are loaded loads the view again at once; set_alignment_options takes the same keys, refuses a bad value by name and answers with every option as it stands
- Reset to Global Defaults resets every colour of the track; it missed the multi-secondary, coverage and poly(A) colours and every colour Settings does not hold
- The values read under the pointer follow the coverage strip's configured height; a quarter of the track was assumed whatever was set
- The status tag over the reads ("D2 396r 103rows") is shown only under VX_DEBUG_ALIGNMENT=1
- A placed unmapped read is drawn as a box with a cross at its position, and can be hovered and read; it was drawn zero wide, so not at all
- A read made secondary by minimap2's tp:A:S or tp:A:I tag alone is drawn as a flagged secondary is: fainter, with the dashed outline; it was drawn in the secondary colour at full strength

### Read aggregate tracks

- The bin under the pointer is read out (value, counts, span) in the status line and the click popup; they are in the SVG export as drawn; they follow intron collapse; aggregate_rows says how it counted and within what span

### Track panel

- A spin button takes the mouse wheel only while it has the focus, so scrolling the panel no longer changes values on the way; an open row's controls follow an option changed through the API or a session
- The remove button of a row removes that row's track. Whichever row's button was clicked, the last track of the list was removed, and a row's visibility switch also set the last track's

### Gene annotations

- A RefSeq GFF3's marks of a partial translated region (start_range or end_range with a dot on the open side, read by the strand) are read, so a transcript whose translated region begins before the sequence has no start found; they were not read, and every such start counted as found
- NCBI's prefixes (gene-, rna-) group a RefSeq GFF3 into genes and transcripts as Ensembl's (gene:, transcript:) do, in memory and through the gene index alike; a RefSeq file gave three index entries for one gene, and in memory its mRNAs were keyed by the gene
- A line whose start reads 0, a line of a gene on another chromosome than its first line's, and a landmark line (chromosome, scaffold, region) are read by one rule in memory and through the gene index, a transcript without a transcript line ends at its exons' greatest end, and the index's two readings share one rule; each of these differed between the two ways
- start_codon lines and the cds_start_NF tag are read (every value of a repeated tag kept), and the gene index (now GDX6, an earlier index rebuilt once) keeps whether the file has start_codon lines; neither was read
- A GTF whose attribute tokens each sit in a tab field of their own (as the published Case 2 file does, on all its 49,865 lines) is read, and one warning line in the log names the file and the count of such lines, once a load, in memory and through the gene index alike; it loaded as a track without genes
- A gene's strand is that of its first record that has one, in memory and through the index alike; a gene line without a strand gave the gene none below 50 MiB

### Transcript structures

- A GTF whose attribute tokens each sit in a tab field of their own gives its structures, with the one warning line in the log, and a GFF3's exon, CDS and UTR lines join their transcript by its Parent whatever the prefix; such a GTF gave none, an Ensembl GFF3's CDS lines were lost, and an exon's Name was taken as the transcript's

### FASTA

- A sequence line with a space or a tab before one of its bases is refused by name with its line number by every reader; a file read into memory kept the blank as a sequence character

### File choosers

- Every pattern (GTF, GFF, GFF3, BED, bedGraph, WIG, BAM, SAM and session files) matches without regard to case, as the FASTA patterns have since 0.9.6; X.GTF was hidden under the annotation filter

### The error counter counts errors and warnings only

- A completed transcript structure index and a transcriptome BAM's notice are information, in the log and the status bar; each read as "1 error" after a good load

### Signal tracks

- The loading lock is released on every exit of a load, a failure included; it stayed set after a load that succeeded and was never set on the progress path
- A BigWig track is drawn from windows read on demand at the file's own zoom levels: the chromosome in view with padding, at the level whose bins are at or below the bases per pixel (the raw records when none is), read again when the view leaves the window or another level is right. Until 0.10.0 a BigWig track showed its first chromosome's first million bases and nothing else
- The value shown for a click on a signal track is the value of the stretch under the clicked base on the chromosome in view, and nothing in a gap; until 0.10.0 it was the nearest start within a window, looked up across every chromosome
- A bedGraph record of up to 10 bases is one value over its stretch, like every other record; until 0.10.0 it was one value per base
- A BigWig zoom block whose length is not a whole number of records is refused by name and nothing is read from it
- A value covers the stretch its record gives. A bedGraph, Wiggle or BigWig record longer than 10 bases was kept as a single point: an analysis took it for one base, an output stretched it to the next record across any gap, and the display drew a file in bins as a comb. Wiggle positions are read as 1-based (every value stood one base to the right). A bedGraph whose columns are separated by spaces is read (it loaded as an empty track), and one that is not in order is put in order
- The plot spans the track's whole width, so a signal stands where the ruler says. It was drawn 50 pixels to the right, the width of its axis; the axis is now a strip over the plot's left edge, with the signal showing through
- Asinh can be chosen, smoothing is in bases, the axis labels the values drawn on log, square-root and asinh scales, and gradient colours follow a value's height; Asinh showed Linear, smoothing under 200 bp did nothing, and every value from 1 up had the top colour

### Read name search

- A BAM the reader refuses part way ends the search with the refusal shown ("BAM search failed"); the alignments found before it were shown as if the search were complete

### SAM files read as coverage

- One rule, every mapped record's aligned bases (an intron's N not counted) with no cap on lines or bases; one loader capped at 100,000 lines and 200 bases a read

### Strand Bias

- The fraction is computed in double precision; two bins in 46 of the validation matrix differed from a direct tally in the sixth digit

### GC Content

- The summary's chromosomes counts the chromosomes written; it counted the ones selected, a chromosome without bases among them

### Save selected track(s)

- A BAM's save answers what it writes, the reads loaded for the view as BED, and the button's tooltip says so; it answered as if the file's records had been saved

### Screenshots

- Every capture is rendered, the window drawn into an image at any scale from 0.25 to 8 (its tracks are the frame drawn at the screen's resolution, enlarged; the viewport capture is the one that draws the tracks at the scale asked) and the viewport or a track off screen, and a capture that cannot render answers an error naming the reason; the window was copied from the screen, so a screen saver or a locked or sleeping screen gave a wrong image (seen on Windows), a scale below 1 was ignored and a failure was an empty 500
- Every image the API returns is opaque: it is flattened on the theme background and stored without an alpha channel. Images carried partial transparency in up to a third of their pixels (up to half in a single track), which document viewers show as grey blocks
- A single track is captured whole wherever it sits in the viewport; a track below the visible area came back as a strip one pixel high, and a track cut by the window's lower edge came back cut
- A viewport capture at scale 1 is rendered off screen like a scaled one, the viewport alone as it is now; it read the window back, took the toolbar in, cut the bottom and could return an earlier capture

### Track height through the API

- set_config trackHeight is the default height of the tracks added from then on, apply_to_existing sets it on the active group's tracks, and a value below 10 is refused by name; it overwrote every existing track, reached no new one, and an integer failed

### Recording through the API

- start_recording's parameters are the recording's own and are checked; they were written into Settings and saved

### SVG export through the API

- text_scale, track_scale and include_overview can be given, and the MCP tool sends only what the caller gave; the tool overrode every Settings value with its own defaults

### Analyses

- Window Overlap and Gene Body Overlap are gone from the list, and run_analysis names an unknown analysis as such; they were listed without a handler
- Every one of the 47 runs where it is asked to, by one rule. A chromosome given by name (with start and end, or alone for the whole of it) is the region; otherwise the scope decides: the window in view, the whole chromosome in view, or every chromosome of the input tracks. 18 analyses (the interval operations, the variant and interaction analyses, signal against features) ignored the region and ran over everything; a chromosome scope without a reference loaded ran over the whole genome, or read nothing
- Three scopes are offered where four were. "All chromosomes, group" and "Genome-wide, all groups" did the same thing; both are now "genome" (the words group and all are still taken)
- A chromosome is found whatever a track calls it (chr1 or 1, chrM or MT), by the rule the viewer itself uses; two tracks that named a chromosome differently were compared as two chromosomes, so a difference of two such tracks gave each track alone and an intersection gave nothing
- A parameter that does not parse or is out of range fails the analysis and names itself; it was replaced by the default without a word. A window, bin size or bin count of 0 never ended or closed the viewer (a division by zero)
- The answer to analysis_status says which scope and region were applied and gives every parameter the analysis read, as applied; output tables list chromosomes in name order (several followed an arbitrary order)
- A run on a reference of very many sequences (a transcriptome of 200,000 transcripts) starts at once; each run spent more than half a second on the list of names before it read anything
- One default for each parameter. What a request does not name is the value of Settings, Analysis, as it always was; the other numbers that the code held for the same parameters, and never applied, are gone
- Mismatch Rate (API MismatchRate), the analysis the name "Per-Base Mismatch Rate" promised: in each bin, the aligned read bases (M, = and X) that differ from the reference base under them, over the aligned bases compared; a base that is not A, C, G or T on either side is in neither count, and inserted bases are the Edit Rate's. It needs the reference loaded and reads it in stretches of whole bins, never for a read
- Interaction Enrichment (API InteractionEnrichmentOverExpected), the enrichment the old name promised: for each feature, the anchors on it against those expected if each anchor of the chromosome were placed at random, the ratio and a Poisson upper-tail p-value; the chromosome's length is the loaded reference's, else the largest anchor end
- An analysis that fails is written to the log as an error with its reason, under the analysis's name; the reason was in the result only

### File formats

- CRAM is not read and the formats list no longer names it; the 0.9.0 entry that said so was wrong

### Interface

- At interface scales above 1.0 the left panel's content and the toolbar were cut at the right behind scroll bars; the panel's width and the toolbar follow the scale now, and the toolbar's groups wrap onto further rows when the window is narrower than they are
- A one-shot timer of the window (a status revert, a saved toast's dismissal, an export poll, the usage prompt) could be lost if the collector reached it first; every such timer is held until it fires
- A desktop theme changed while VX runs is followed at once, not at the next change of scheme

### Popups

- The click information popup is measured before it is shown and opens above the click where it fits, else below, and in a window too short for either on the side with more room, its text cut to fit with a scroll bar and at least four lines in view; its height was read as 0 before it was shown, so the toolkit chose the side and put a popup taller than both rooms beside the click
- The popup's body is drawn in DejaVu Sans Mono, registered for the interface at start from the file VX_FONT_FILE names or from fonts/ beside the program (a system with neither that file nor the font uses its monospace), where it was the host's monospace (Courier New on Windows)
- A gene's, a feature's or a loop's popup never found its element, so it showed the region alone; the element a click finds carries its chromosome, and the popup, the status line, the TSV, the gene copy menu and a bookmark's label name it

### Settings

- The Min MAPQ tooltip says that the floor reaches the six quantification analyses as well as the alignment statistics
- Hotkeys are captured by one click and one key and work when Settings closes, Track Styles reach tracks loaded afterwards, the selection halo, corner radius and speeds are drawn as set, and controls that changed nothing are gone; each click added a key handler that took every later key, and many settings were stored only
- A shortcut captured in Settings > Hotkeys is saved with the platform's shortcut key (Control, or Command on macOS), and the Hotkeys tab shows Command as Cmd on macOS

### Command line

- --headless runs the viewer without a window, with every loader, analysis and API command available on the configured port or --port N, until a shutdown command or --exit-after SECONDS of idleness; --analysis TYPE with --load FILE (repeatable), --scope or --region chr:start-end, --param key=value, --tracks and --out DIR loads the files in order, runs the one analysis through the same engine and rules as the window, writes the result and its manifest, prints the result's summary as JSON on stdout and exits 0, 1 when a load or the analysis failed, 2 on a bad command line; an analysis without the window needed the window on a hidden display and a client of the API
- --load FILE loads a file at start as a drop would, in the order given (a .vxs file restores that session); an option the viewer does not know is noted in the log and passed on, where it stopped the reading of every option after it

### Results

- Every result file gets a manifest beside it (<result>.manifest.json): the analysis, the version and build date, the time, each input file with its size, modification time and SHA-256 (files up to the Settings limit, 1024 MB by default, or any size with hash_inputs=true), the parameters as applied, the scope and region, each output file with its size and SHA-256, the summary and the elapsed seconds; a result file stood alone

### Quit

- Ctrl+Q closes the window through its normal close, so the window's size and state are saved, and the Hotkeys tab's Quit binding takes effect; it ended the process at once, and the binding in Settings changed nothing

### Log

- Every entry of the Error Log (the status bar's count, the dialog) also reaches the log file at its level, once, with a repeated error counted in one line; the two logs never met. The log directory is created readable by its owner alone, since the log holds file paths and the command line
- The viewer writes a log file in INDEGRA's levels and line format ([2026-10-07>>03:40:05.12] [WARN ] [        52.3 MB] [GCContent] message), errors and warnings by default, one file per run in the platform's place for logs (Linux ~/.local/state/vx, macOS ~/Library/Logs/VX, Windows %LOCALAPPDATA%\VX\logs), the last 10 kept; the logger formatted every message and dropped it, so no warning or error reached anyone
- VX_VERBOSITY=tXlY or --verbosity tXlY sets the terminal (stderr) and the log file apart (-1 off, 0 errors and warnings, 1 basic, 2 detailed, 3 debug, with file and line on debug and error lines when the terminal is at 3); the terminal is off unless asked, so a run stays silent on stdout and stderr; the log file's level is in Settings, Paths, Log File; --verbose, --debug and --quiet, which set the level of a logger that wrote nothing, are short forms of --verbosity 1, 3 and t-1l0
- The startup banner, printed on stdout at every start, and the errors and warnings of the renderers, loaders, indexes, the configuration and the plugin loader, printed on stdout, go to the log at their level
- A second launch, which activates the viewer already running and exits, says so on stderr (VX: another instance owns org.biocodecs.vx on this session; it was activated and this process exits. Set VX_NEW_INSTANCE=1 for a second viewer.) when stderr is a terminal, besides its warning in the log, so that a launch from a desktop icon stays silent and a terminal user sees why nothing opened; the message was never written on GLib 2.88, as the check came after GLib had unregistered the application and printed a GLib-GIO-CRITICAL assertion line on stderr instead
- A log file at debug level (VX_VERBOSITY=t-1l3, or Debug in Settings, Paths, Log File) gives the source file and line of its debug and error lines whatever the terminal's level; only a terminal at debug added them, as in INDEGRA
- The memory column of a line is the process's resident memory and then the garbage-collected heap in use ([        96.2 MB /          1.7 MB]), named in the log file's header, with ? for a reading that failed; it was the garbage-collected heap alone, 1.7 MB where the process held 96 MB
- The gene index's, the reference sources', the track panel's, the reads renderer's and the main window's last 24 direct messages (Loaded cytoband data among them) go to the log at their level; they were printed on stdout

### Start

- A standard descriptor closed at launch is opened on /dev/null, so a later write to stderr cannot land in a data file; on Windows a notice that would go to a terminal the viewer has none of is shown as a message box
- The Snapshots directory is no longer created at every start; each export makes its directory when it writes
- Fonts are found through fontconfig's library, loaded at run time, so fc-cache no longer runs at every start (the library reads its caches and rebuilds a stale one when it first needs it), and fc-match and fc-list are no longer run as processes; a host without the library starts as before, with the shipped font and the platform's font directories

### The program is VX

- The executable is vx (vx.exe on Windows, VX.app on macOS); the window's title, the About tab, the log file's header, the API's ping, the SVG export and the MCP server say VX; the settings file beside the executable is vx.cfg, and a genome-viewer.cfg found there when no vx.cfg is, is read once and the settings saved as vx.cfg, the old file left as it is and a line in the log saying so. A 0.10.0 launch no longer activates a running viewer of an earlier version: the two run side by side

### Snapshot

- "Transparent background" gives a transparent background in PNG and TIFF, stored with straight alpha; the option had no effect. A JPEG is always opaque

### Analyses on alignments

- Peak calling, gap detection and the analyses that read an alignment track as a signal (difference, ratio, z-score, enrichment, prominence, correlation, signal at features, heatmap, profile) read a BAM one reference at a time and keep one counter per base, no reads. Peak calling over a whole 23 GB BAM takes under 3 minutes within 1.3 GiB of memory; it passed 46 GiB without finishing its first step
- At viewport or region scope, peaks and signal values are reported at their own coordinates and only inside the window asked for; they were offset by the start of a window padded by half its length on each side, and included the padding

### Gap detection

- A gap no longer runs past the end of a chromosome (every chromosome ended in a gap half its length that does not exist); at viewport or chromosome scope only that window of that chromosome is read, where the whole BAM was read and every other chromosome reported

### Feature tracks

- A file or an analysis result with its features in coordinate order no longer slows the viewer down or stops it. 20,000 sorted BED lines took seconds, 60,000 on one chromosome ended the viewer, as did an analysis that returned as many; 500,000 now load in under a second

### Feature and gene tracks

- Features added in more than one batch to the same chromosome are all kept; a later batch replaced the earlier ones

### Settings, Analysis

- Every value shown is applied, or is gone. The minimum read count, minimum allele frequency, minimum MAPQ and maximum insert size were shown and never applied; they are applied now and start at "keep all" (0), and a configuration saved by an earlier version is put there once, so that no result changes without your choosing it. The significance level is removed: no analysis has a test for it
- Each row says which analyses read it (hold the pointer over it). "Z-score threshold" is now "Prominence multiple (N)", "Signal threshold" is "Threshold (times the background)", and the frame "Signal Analysis" is "Sliding Windows": the names say what the values do

### Alignment statistics

- On a BAM without an index, the first record of every reference after the first was lost; a reference shorter than 100 bases was skipped (every reference of a small RNA transcriptome); the last bin of the strand bias, soft clip and mismatch tracks ran past the end of its chromosome. A BAM without an index that is not sorted by coordinate is refused by name: a part of its records was read as if it were all
- One rule says which records the eight count: mapped, primary records (samtools view -F 0x904), at or above min_mapq; primary_only=false adds secondary and supplementary records, ignore_duplicates=true leaves duplicates out. Every result says how many records it read and left out, heading by heading. Every record was counted, whatever its flags
- A record's bases can be read one at a time from the packed sequence field; the statistics that do not read them pay nothing
- At genome scope the records with no reference are read and left out as unmapped, so records_read and skipped_unmapped are what samtools flagstat and samtools stats count; they were never read (79,910 of the 87,042 records of the yeast test BAM)

### BigWig

- Files written by the standard tools are read. Their data blocks are zlib streams and were opened as another kind of stream, so every such file loaded as an empty track, without a word. The analyses and the export read the whole file, one chromosome at a time; the display still shows the first million bases of the first chromosome (the rest is to come). A BigWig that cannot be read fails its load and says why

### Signal at features

- One rule for every kind of signal: mean_signal is the mean over the bases that have a value and coverage their number, and a new column, mean0_signal, is the mean over the feature's whole length. A coverage track gave the second under the first's name. An alignment track is taken as the signal (it was refused)

### Heatmap matrix and profile

- A feature nearer the start of its chromosome than the flank keeps each column in its place; its columns were moved to start at the chromosome's first base, so each held another stretch than its heading said
- A feature on the minus strand is read in its own direction. Its row's bins are the mirror image, about the feature's midpoint, of a plus-strand feature's, so the first column is upstream of every feature (as deepTools' computeMatrix turns such a row over). The strand comes from the BED column or the annotation; the gene index saved beside an annotation now keeps it (format GDX4), and an index of an earlier format is rebuilt once
- With more bins than twice the flank, every bin reads the signal under it, so a feature's row is the same whatever else the region lists; the bins past the flank read nothing unless another feature listed reached them

### Gap detection on a signal track

- A gap is a stretch with no value above 0. A stretch the file left out was filled with the value before it and never reported, and a value below 1 always was

### Contact frequency against distance

- Each distance keeps its own score (the distances were put in order and their scores were not), and the largest distance is counted. TAD boundary detection: the insulation values are numbers (every one was written as nan, and no boundary could be called)
- The median is the middle value (it was the upper of two), and the linear bins have one
- The log-bin edges are exact and the same on every system; an edge whose value is a whole number came out one less as often as not, as the C library rounded

### Variant analyses

- Positions in the intersection table are 1-based, as in the other variant tables; the density windows end at the chromosome's end; the hotspot threshold and width can be set (they were fixed at 3 and 1 whatever was asked)
- A variant is an alternate allele. A record with two alternate alleles is two variants, each reduced to the bases it changes, and an entry that states no variant (a missing allele, the marker *, a gVCF's unnamed allele, or the reference itself) is in no table and is counted. The first allele alone was read, and a missing allele was counted as a SNP and as a transversion

### Motif search

- The result's track holds the matches (it came back empty). Quantification from a signal track: a value counts over the stretch it covers, not up to the next value. Bin statistics on a BAM bins every reference, one under 100 bases too
- Both strands. The reverse complement of the motif is searched as well, and a match of it is written with strand "-" (a match of the motif itself with "+"; every row said "."); the parameter strand takes both (the default), forward or reverse. A motif is IUPAC codes, not a regular expression. The default file name holds at most 32 letters of the motif: a motif of 10,000 letters, which was accepted, gave a name the file system refuses, and the run failed
- On a transcriptome reference the default strand is forward (the minus strand of an RNA is not in the sample); on a genome it is both, as before. A site that both strands match (every site of a motif that is its own reverse complement) is one row, with strand "."; it was two, "+" then "-". The summary says the strand searched, the default, and the rows of each strand

### Catalogue

- The Ts/Tv ratio, the coding impact and the mismatch rate are offered without a reference loaded (they read none); the nucleotide frequency is listed as the table it writes; an analysis that is listed but not in this version is refused at once
- Each analysis's line says what it computes; Export Track Data is no longer offered the reference's own track, which it refuses

### Analyses on a transcriptome reference

- The middle scope is the transcript in view. The Run Analysis dialog says "Full transcript" and "All transcripts" where a genome gets "Full chromosome" and "All chromosomes", and run_analysis takes the scope "transcript" as another name for "chromosome". The word was taken without complaint before and the analysis ran over every transcript of the reference

### Run Analysis dialog

- The analysis that is clicked is the one that runs. Whichever button was clicked, the last analysis of the list ran (Repeat Density with a reference loaded); "Run All Applicable" and the API were not affected

### Read menu

- An entry under "Other Alignments" or "BAM Alignments" goes to the alignment it names (every entry went to the last one listed). Missing files of a session: each "Locate..." button asks for its own file (every button asked for the last one). Save Track(s): the progress names the track being saved

### Per-Exon Coverage and Bin Statistics

- The depth of a BAM follows each read's alignment, as in the other analyses (clipped bases and introns were counted as covered, and secondary and supplementary records were in); a region lists the exons or bins that meet it, each computed whole, where it listed every exon or bin of the chromosome with the region's reads alone

### Bin Statistics on a signal track

- A statistic weighs each value by the bases it covers and a bin without a value is left out (a value counted once whatever it covered, and an empty bin was written as 0); "median" is a median (it gave the mean)

### Peak calling

- A peak is a stretch of consecutive bases at or above the threshold times the background, which is the median of the values above 0. Where nothing reached the threshold it used to be lowered until something did, so a chromosome of even coverage came out as one peak from end to end; now a track without a peak has none, and the result says so with the background and the cut-off. A base without coverage ends a peak (a peak ran on across uncovered stretches, an intron between two exons included)
- Stretches no further apart than the "Max merge gap" of Settings are one peak (the setting was shown and read by nothing; max_gap in a request), and bg_window, when given, keeps a peak only if it also stands above the bases around it

### Enrichment over input and feature prominence

- A stretch ends at its own last base (it ran on to the next stretch below the threshold, across bases without a value); max_gap joins stretches and min_width drops short ones in both

### GC content

- A request that names a window of its own and no step has its windows end to end; it was given the step of Settings (500 bases) under any window, so windows of 100 bases stood 500 apart
- S counts as GC and W as not; N and the other ambiguity codes are left out of the count (every character but N was counted, and S was not GC)
- With a step below the window each value is written, in the file and on the track, over the step at its window's centre (the first span from the region's start, the last to its end), so the records tile the region and never overlap: bedGraphToBigWig takes the file at any window and step. The value is still the whole window's. Each value stood over its whole window, so the Settings default (1,000 every 500) wrote overlapping records, which bedGraphToBigWig refuses and the viewer read back cut at each next start

### GC content, CpG density and repeat density

- The last window of a chromosome or region is written, shorter than the others, and a sequence shorter than one window has a window (CpG density and repeat density wrote none; GC content left out what did not fill a window)

### CpG density

- A CpG whose C ends a window counts for that window (neither window counted it)

### Repeat density

- Two different k-mers that hold ambiguity codes other than N are no longer taken for one

### Ts/Tv ratio

- Every alternate allele that is a single-base substitution among A, C, G and T is counted once; the total of a region is named by the region (it said GENOME); with nothing counted the ratio is NA
- On a region a chromosome's row is the whole chromosome's, and the region's counts are in the row named by the region; the chromosome's row held the region's counts

### Variant intersection

- Two variants are one when they are the same allele at the same place (the same position was enough: C to T was shared with C to A)

### Allele frequency spectrum

- A variant's frequency is AF, else AC over AN, allele by allele, the same rule the frequency floor reads; a variant without one is counted and is in no bin (where no variant had a frequency, every variant was given 0.5)
- The bounds are printed with four decimals when the number of bins does not divide 100; they were printed with two, so at 3 bins the bound 1/3 read 0.33 while the bin followed 0.33333334
- A frequency is counted in the bin whose printed bounds hold it; from 22 bins on, some frequencies equal to a lower bound fell in the bin below (AF 0.53 in [0.52, 0.53) at 100 bins)

### Variant annotation

- A variant's place goes by the transcript's strand and by a stated order of rank (splice acceptor, splice donor, translon, 5' UTR, 3' UTR, non-coding exon, intron), over every transcript it meets; the table names the transcript, and the distance to the nearest gene for a variant between genes. No UTR was ever named, donor and acceptor went by genomic side, and the distance was 0 or a dot

### Coding impact

- Each codon is read from the reference in the transcript's own direction and translated: start lost, stop gained, stop lost, synonymous, missense, frameshift and in-frame insertions and deletions, one row for each variant and coding transcript, with the codons and the amino acids. It translated nothing. It needs the reference the variants were called on, and checks REF against it
- Multi-base substitutions, complex alleles and indels are translated over the codons they change, with the codons and the amino acids in HGVS's one-letter forms (K2_K3delinsNQ, A5del, W6_Q7insG, A5Lfs*5), and a change across an exon's edge is named by the splice site it reaches; they were not translated, and an indel had no codons
- An indel in a repeat is left-aligned against the reference before it is placed, as bcftools norm does, so that two spellings of one change give one row, and the new column normalised shows the allele so written; it was placed where its record wrote it
- A translon (the annotation's CDS) has a start where the annotation found one (a start_codon line, or in a file without start_codon lines no cds_start_NF tag), whatever its first codon, and none where it did not; any CDS that began on an initiation codon of the code was read as having one, so 20 CDS on chr19 without a start_codon line had one
- A start the annotation found is read as Met whatever its codon, as VEP reads it with Ensembl's initial-Met edit, and a change of it is start_lost unless the new first codon reads Met by the code (CTG to TTG and CTG to CTA lost, CTG to ATG kept, ATG to ATA kept on the mitochondrion); a start other than ATG was kept by any initiation codon of the code, so CTG to TTG kept it, and before that ATG to CTG or TTG kept it too (M1M)
- A new last column, near_cognate_start, says on a row that alters a start codon whether the codon then at the start is ATG or a near-cognate start (the built-in CTG, GTG, TTG, ACG, ATA, ATC and ATT, the one-base neighbours of ATG reported as initiating, or a list the user loads: the parameter near_cognate_list, Settings > Analysis), and the summary names the list in use; the table said nothing of it
- Bases put in at a start's first base that leave the three start bases intact are a 5' UTR row on either strand, as VEP places them; on a reverse-strand transcript the left alignment put them inside the start codon or after it, so ACG put in before ATG was start_lost and ATG put in before ATG an in-frame insertion (M1dup)
- A deletion at a start the annotation found is read at its 5'-most placement along the transcript when that placement meets the start codon or lies wholly before it, as an insertion is, so that both strands give one row for one change: the start's first base taken out, the base before it the same, is a 5' UTR row on either strand, and a deletion that still meets the start codon after the slide is read there (its translon_pos and codon_change at that placement); on a reverse-strand transcript such a deletion was read where the left alignment on the genome put it, inside the start codon (a frameshift or start_lost), while the forward strand gave a 5' UTR row
- The column near_cognate_start reads bases put in at their 5'-most placement along the transcript, as they stand there, whatever placement the row keeps, so that a G put in between the T and G of ATG answers yes on either strand; on a reverse-strand transcript the column followed the row's place after the start codon and answered '.'
- A change that leaves no base after it (a translon of its start codon alone at the transcript's end, taken out whole) writes no in near_cognate_start; it wrote '.'
- An in-frame deletion or duplication in a repeat is named at its last place by HGVS's 3' rule (A5del, A5dup, K4_A5del), the change kept where the left alignment puts it on the genome; it was named at the run's first place (A4del) and a duplication was written as an insertion (K3_A4insA)

### Variant density hotspots

- A hotspot is a run of windows with at least three times the median count of the windows that hold a variant; a call set with one variant a window has none (the whole chromosome came out as one hotspot)

### Closest feature

- Exact, and every tie is written. A long feature of the second track that covers the first is found (four features around the midpoint were looked at). The distance is 0 for a shared base and otherwise the bases between and one more, as bedtools closest counts; the direction says upstream, downstream or overlap by coordinate (it said downstream on both sides)

### Interval operations

- A coverage, signal, alignment or variant track in the place of an interval track is refused by name (the subtraction and the union answered as if it were empty)

### TAD boundary detection

- An insulation score after Crane et al. (2015) on the listed interactions, with window_size applied, and boundaries at its minima (min_strength). The old value was highest where the boundaries are, and no boundary was called where most bins were empty

### Interaction enrichment

- Anchors and interactions at each feature are counted apart (anchor_count, interaction_count), through an index: 20,000 features against 100,000 interactions took 37 s and take 0.2 s. The table computes no enrichment, and now says so

### Mapping quality and insert size

- The median is the middle value, or the mean of the two middle ones. The MAPQ median never looked at 255 and stopped a place early: reads at 3, 255, 255, 255 had a median of 0

### Per-base mismatch rate

- The reads' NM edits over their aligned and inserted bases, bin by bin where the bases lie; the total equals the error rate of samtools stats. A read's whole span and all its edits went to the bin of its first base

### Strand bias, soft-clip frequency and mismatch rate

- A region lists the bins it meets, each computed whole

### Signal correlation

- Spearman's rank correlation beside Pearson's (the catalogue named both and one was computed), exact, over the same bases

### Two analyses named for what they compute

- "Edit Rate" (it was "Per-Base Mismatch Rate": the NM edits, which are mismatches, insertions and deletions together, over the aligned bases) and "Interactions at Features" (it was "Interaction Enrichment": anchors and interactions at each feature, with their scores, and no expectation). Their API names, PerBaseMismatchRate and InteractionEnrichment, are unchanged; their result files are edit_rate_* and interactions_at_features_*

### Settings, Fonts

- The family list and a chosen family work wherever the fontconfig library is present, on Windows and in the macOS bundle too; they needed fc-list and fc-match on the PATH, so the list was empty there and a chosen family was never resolved

### Viewport font

- A file fontconfig names is used only if it exists; a stale answer was passed to FreeType unchecked

### Loops

- A loop reads on the light scheme. The colour ramp of the loops, the signal gradients, the variant ramps and the SVG export subtracted its channels as unsigned numbers, so every ramp that falls in a channel saturated and the loops were drawn white (pale on the dark scheme, invisible on the light one); one ramp replaces the four copies, and the loops' low-score colour follows the scheme unless the user has set the colours. The two score colours are kept in a session
- On the dark scheme the loops of high score are a light coral that reads against the background; they were a dim red. With Intra-chr only off a loop to another chromosome is drawn at its anchor; it was not drawn
- On the dark scheme a loop of low score is near white (239, 239, 245), its line 4.5 to 1 against the track; it was (200, 200, 220), 3.5 to 1
- On the dark scheme a loops track is drawn at an opacity of 0.7 until the user sets its opacity, its median contrast against the track, measured on a test view, 3.0 to 1; every track was drawn at 0.5 on both schemes, 2.2 to 1 on the dark one (the light scheme is unchanged)
- An opacity the user sets in the track's settings, through arc_alpha or in Track Styles is the track's own on both schemes and is kept by the session, and Reset to Global Defaults returns the track to its scheme's opacity; the one stored opacity was drawn on both schemes and could not be told from the default

### Downloads

- The reference sources, the download dialog's size probe and the usage statistics' send go through libcurl, which is loaded when first needed, and a host without it is told "libcurl is not available on this system" while the rest of the viewer runs; the curl program was run for each of them, so a host without it failed all three
- An HTTP error status is an error and leaves no file, every request sends VX/<version> as its User-Agent, and a redirect leads only to an http or https address; a 404 page was written into the downloaded file and reported as a failed decompression, and an error page reached the JSON parser as if it were the answer

### Reference genomes

- A downloaded .gz reference, annotation or cytoBand table is inflated by the viewer itself (every gzip member; a file cut short or damaged is refused by name and leaves no partial file); the gunzip or gzip program was run, and Windows has neither. The cytoBand tables come from hgdownload.soe.ucsc.edu (the cse host's certificate no longer matches its name)
- An NCBI RefSeq download (a zip) is unpacked by the viewer as a stream, in two 1 MiB buffers whatever its size, zip64 archives and members of 4 GiB or more included, every member's CRC-32 and local header checked against the central directory, a name that would leave the folder refused, and the genome left where it was asked to be put; the unzip program was run and the genome it unpacked was then deleted, so the download reported success for a file that was not there
- A reference with a sequence of a million bases or more is a genome however many sequences it holds, so GENCODE's full GRCh38.p14 FASTA (706 sequences) has a genome's overview of its 24 chromosomes, the scope words Full chromosome and All chromosomes, and Motif Search on both strands by default; it was taken for a transcriptome, and Motif Search read its forward strand alone

### Usage statistics

- A send is a failure when the endpoint answers with a status other than 2xx ("Send failed (HTTP 500)"), and a redirect is not followed with the payload; any answer was reported as "sent"
- The operating system version and memory (macOS: sysctlbyname; Windows: RtlGetVersion) and the screen size (GDK's primary monitor, passed in by the caller) are read by library calls and no program is started; sw_vers, sysctl, cmd, xrandr, system_profiler and PowerShell were, and a host without one sent an empty field. The payload's ten fields are unchanged

### Coding impact and variant annotation

- The annotated translated region is named translon (Swirski et al., Nature Methods 22, 2025): the column cds_pos is translon_pos, and the annotation's place exonic is translon

### Variant annotation and variant intersection

- With the reference loaded, an indel is left-aligned before it is placed or matched, as coding impact does, so two spellings of one change are one place and one variant; they were placed and matched as written

### Gene annotations over 50 MiB

- The interval operations and Save Track's BED give each gene its strand, as the gene index holds it; every gene had none there, where a smaller file gave each its own

### Region Differential

- A region of the regions track that the window cuts is computed over the whole of it; it had the numbers of its part inside the window, printed under its full bounds

### Z-score normalization

- A value that is not a number ("nan" in a bedGraph) is no value, left out of the mean and the deviation and given no row; it made the mean, the deviation and every row "nan"

### Edit rate and mismatch rate

- The bases of a read aligned past the end of its reference belong to the last bin, where the edit rate counts them and the mismatch rate, with no reference base to compare, leaves them out; the mismatch rate dropped the read's whole last piece, and the edit rate counted such bases or not as the bins fell

### Interaction analyses

- An anchor whose end is before its start is read as the anchor between the two numbers; its midpoint went round 2^32, giving it a distance of about two thousand million bases, and it met no window and no feature

### Bin Statistics

- With a reference loaded, a chromosome's last bin ends at the reference's length for it (bins of a BAM or coverage track past its end are 0, those of a signal track without a value are left out); the last bin ended where each input ended

### Variant density

- A record is counted in the window of its first base at any scope, so a window has the count it has at genome scope, and one that reaches into a region from before it is counted in the summary; it was counted in the region's first window

### Chimeric Read Density

- On a region each cluster that meets the window is built from every record of it, wherever they lie, and has the numbers genome scope gives it; a cluster at the window's edge held only the records that reached the window, often too few to be written, and one that passed over the window was not seen

### Contact Frequency vs Distance

- A region lists the interactions with an anchor in its window, each at its whole distance; an interaction needed both anchors in the window, so a window's decay held no distance longer than the window

### Interval Subtraction

- On a region an interval of A is less every interval of B that meets it, wherever that lies; B was taken in the window only, and an interval of B beyond the window was not subtracted

### Interval Union

- On a region a merged interval that meets the window is merged from every interval that joins it; the intervals beyond the window were left out, so it was shorter and its count lower

### Insert Size Distribution

- Whether there are pairs is decided by the records counted in the region; the file's first 10,000 records decided, so a file whose first 10,000 records were single reads was called unpaired though its later records were pairs

### Interactions

- A missing score (".", an empty or absent column, or text that is not a number) is no score: it is left out of every sum and mean, written "NA" in a table and "." in a BEDPE export, and counted in interactions_without_score; "." and text were read as 0, and an absent score printed "nan" in the contact decay, the table at features and the export

### Interactions at Features

- The mean score of a feature with no scored interaction is "NA"; it was 0

### Loops on the display

- A loop without a score is drawn at the low end of the score ramp, its popups say "none" or "NA", the track's score range is over the scored loops, and a minimum score the user sets above 0 hides it; its colour, range and text went through as NaN

### Motif Search

- The default file name names the region searched (motif_ACGT_chr1_100-200_ and the time); it said "genome" whatever the region

### Large annotations read through the gene index

- A gene whose lines take more than 4 MiB of the file is read in pieces; it was left out without a word, from the display and from every analysis

### Dark scheme

- Ctrl+D, Settings and a restored session switch the viewport's scheme at once, and a viewer started dark draws it; they changed the stored value only, and a dark start drew the dark scheme's pale text on the light colours
- The window's controls, its dialogs and the status bar take the dark scheme with the viewport (GTK's dark variant, or Adwaita's where the desktop theme has none), and their fixed colours are lightened where needed to be read on it; they kept the desktop's light theme around a dark viewport, and with a dark theme the status bar's colours were dark on dark
- The alignment panel's warning over a transcriptome BAM is lightened to 4.5 to 1 on a dark theme ((213, 142, 43) on Adwaita's dark); it was drawn #CC7700 on any theme, 3.6 to 1 on dark

### Sequence track

- Show bases and Show GC% take effect, and the GC curve counts GC as the GC Content analysis does; both switches did nothing and the curve counted S as not GC

### Coverage tracks

- The Log scale is drawn and the Heatmap colour mode colours each column by its depth; both were stored only or one colour

### Overview

- GRCh38 centromeres are drawn on GRCh38 chromosomes only, and Bands draws no made-up bands; Arabidopsis Chr1 showed human chromosome 1's centromere at 95%

### Window and toolbar

- The window opens at its last size; Grid, grid colour, opacity and Scale show and save the values in use; they started at fixed values

### Control panel

- Re-index and Clear Cache are gone; they acted on a cache nothing used and reported success

### Variant export

- The records are written as read, every ALT entry, INFO field and genotype column kept, under the file's own header lines; INFO was replaced by the record's type and first AF, and the genotypes and the header were dropped

### Reads

- An alignment track's reads can be sorted by start, end, read length, length on the reference, mutation extent (edits per alignment column), modification extent (calls per read or per base), MAPQ or strand, either way, and grouped by type (primary unique, primary multi-mapped, secondary, supplementary), strand or HP tag, each group in rows of its own under a labelled band; until now the panel had start order only and the API's end and length orders and class blocks had no band
- Filters by read length, MAPQ, mutation extent, modification extent and SAM flags apply as the reads load, before the Max reads subsample, so the reads shown are a sample of the reads that pass, and the first band says how many the filters hide
- The layout no longer reorders the reads, so a mate line joins the read's mate; it joined another read wherever the sort moved reads, which a sort by end or length did and the start order did among reads of one start; with no key set the rows are those of before, read for read
- A sort other than by start fills the gaps of upper rows; it could only add a read after a row's last one, up to a row per read
- At density 4 every read in the track's area is drawn; the drawing stopped at the first read below the area, and reads after it in the list (with groups, whole groups) went undrawn
- A right click on a read selects it and opens its information at every density level, and on a read already selected opens its menu; it opened the menu only, with nothing selected

### Modifications

- A call is a diamond with an outline in its type's colour (5mC purple, 5hmC pink, 6mA teal, other codes slate; lighter on the dark scheme), at least 6 px across, opaque as its probability, and the legend lists each type shown; the small dots in the hues of the mismatch colours remain as the Classic style
- At full detail and read blocks a mark grows under the pointer, a click selects it and a right click gives its information: the code and its names, the probability ML/255, its base in the read and on the reference, the read's name and strand, then the read's own text

### Base modifications

- The MM and ML tags are read as the SAM tags specification states them: a reverse read's modifications sit on the bases they name (they were counted from the wrong end of the read and landed on other bases or were dropped), each code of a group such as C+mh has its own probability (the first was given to every code), the older Mm and Ml tags are read, and tags that do not fit their read are refused instead of read as far as they go

### Poly(A) tails

- A tail given as a float (pt:f) has its length, rounded to the nearest base; it read as 0 and was never drawn. A tag read as an integer gives the caller's default when it is of another type, so a HISAT2 read's ZS score replaces its XS strand tag, which read as a score of 0

### Alignment strips

- The modification-frequency and mutation strips and their hover percentages count their reads and divide by the depth of the same reads, every read the load fetched; they counted the subsample of max reads and divided by the depth of every read, so that 500 reads of 10,000 showed a twentieth of the frequency. Their mean probabilities and the poly(A) strip's means are numbers (they were NaN), and a tail of 0 is no longer counted
- At views wider than about 2 Mb the modification, poly(A) and mutation strips hold their counts in the coverage strip's bins, each bin's frequency or rate its own counts over its own read bases, and their readouts name the bin; each strip held arrays the length of the whole window (about 4 GB of memory for the modification strip at a whole chr19 view)
- The modification, mutation and poly(A) strips' readouts say that their depth and their count of tails are of the reads held ('[mean 12.9x of the reads held]', '(n=2 of the reads held)'), the reads kept for drawing, a sample when the window holds more than Settings' BAM max records per query; they gave that sample's depth as though it were the window's, where the coverage strip, which counts every read, said 319x

### Modification density track

- Added from an alignment track's settings, its read menu or the API (add_aggregate_track), it counts the modification calls of every read in view, not the subsample, and shows each site's stoichiometry, mean confidence and coverage as bars, a line or a heat strip, with colour, opacity and height each mapped to a statistic in its settings

### Poly(A) tail track

- Added the same way, it shows the tail lengths of every read in view by bin, as bars (median or mean), box plots or violins (a Gaussian density of Silverman's bandwidth), with the bin width, the tail's end and the axis in its settings; both new tracks are kept in a session

### Settings, Help

- On a dark theme the help text is light on a dark background; it was the theme's white text on a forced white background

### Track settings

- A loops track's open settings follow a change of colour scheme, showing the opacity and score colours drawn; they kept those of the scheme they were opened on

### INDEGRA's read tags

- In a BAM whose header names INDEGRA (an @PG line whose ID or PN is INDEGRA) each read's INDEGRA tags are read by the type INDEGRA writes (XR, XU, XN, XP, XS, XM, XC, XW, XG, XF, XD, XL, XA and the transcript tags Y5, Y3, YG, YD, YU, YR, YF, YE, YN), a tag written twice by its first value and a tag the record lacks as unknown; VX read none of them, and the same names written by other tools (HISAT2's XS:A, a suboptimal score XS:i, BWA's XA:Z, the transcriptome-to-genome converter's XG:Z, XL:i, XP:i) are still never taken for INDEGRA's

### INDEGRA's categories

- The read colours "INDEGRA allocation" show each read's allocation stage (UNIQUE, BATCH, ABUNDANCE, CLASS_B, UNALLOCATED, other or none) whenever a read the track has loaded carries INDEGRA's XS tag, and otherwise whether it was re-allocated, not re-allocated or has no XR tag, in a palette chosen for each scheme with a legend that says which and counts the reads; the read layout groups the reads by INDEGRA allocation and can hide the re-allocated reads or show them alone; and a read's popup lists its INDEGRA fields in words, those its record lacks named, and its transcript's DTI with where it came from; none of this existed

### Transcript DTI track

- INDEGRA's {sample}_process.txt opens as a track, recognised by its header line (it was refused: "no plugin for extension .txt"), and an INDEGRA BAM's YD tags give one too; it draws each transcript's DTI as a band over the transcript on a transcriptome reference and as a row per transcript of the gene annotation on a genome reference, on a sequential or diverging scale over a range the user sets, labelled, shown or hidden like any track and kept in a session

### Stability

- The pause in which the memory manager stops the other threads leaves their error code as it found it, so an analysis no longer closes the viewer while a file, an icon or a theme is looked up; it left a stale code, and the viewer closed with "getauxval () failed: Interrupted system call"

### Windows

- The demo download and every other web request check the server's certificate against Windows' own certificate store; the package ships no certificate bundle, and every https request failed
- The package holds vx.exe, which opens no terminal window, and vx-console.exe, the same program for a terminal (the command line, --headless, --analysis and its printed answer); vx.exe opened a terminal window beside VX

### Variant annotation and coding impact

- A stop codon that a GTF gives apart from its CDS lines (GENCODE's and Ensembl's stop_codon lines, two of them where an intron splits the codon) is in the translon for both analyses, and the gene track, the popups, the transcript index and the API's translon regions show it there; variant annotation called its bases 3' UTR while coding impact read them as the stop codon

### Chromosome names

- A scaffold is matched between Ensembl's and GenBank's names and UCSC's by its accession and version (KI270721.1 is chr11_KI270721v1_random; the chrUn_, _random, _alt and _fix forms) in the analyses, the display and navigation, and where two names carry one accession neither is used and the log says why; with a GTF named one way and a BAM the other, every exon on a scaffold read no reads

### Active Mode

- The label over the value cursor's dot names a depth over an alignment track's coverage strip ('109182x', 'max 319x (22 bases)' at a wide view, 'not read' where the reads were not read), and each strip's own value elsewhere; it read as a GC percentage ('GC: 10918200.0%') over every track but a coverage track

### Genes

- With intron collapse on, the gene track lists only the genes that show in the view, each in the row it has with collapse off; a gene outside the view, pulled to the view's edge by the collapsed introns beside it, took the first row and pushed the genes in view below the track's visible rows

### Variants

- The click text of a genotype partly called says how many alleles were not called and what the others are (./1 reads "one allele not called, the other alternate"); it said "partly called, alternate". Its drawing is unchanged

### Appearance

- At the first start (no settings file) the colour scheme follows the desktop's dark preference (Linux: the desktop portal's colour scheme, else GTK's dark preference or theme; Windows: the apps' light or dark mode; macOS: the dark appearance) and is saved as the setting; later starts keep the setting whatever the desktop says. The first start was always light

### Shortcuts

- On macOS the keyboard shortcuts use Command where they used Control (Command-O opens a file, Command-D switches the scheme), shortcuts saved by an earlier version included; on Linux and Windows they stay on Control

### Mutation strip

- On a large indexed reference a view wider than 10 Mb is compared with the reference over its whole width, read in pieces of 1 MiB; until now no base past the first 10 Mb was compared and the strip stated there the rate of the deletions and insertions alone

### Gene popup

- A click on a gene names that gene in the popup, its title, the status line and the copied row; it could name another gene up to 50 kb away on an indexed annotation or an overlapping one in memory, and about half the genes' boxes opened a part's popup

### Linux

- The release binary needs glibc 2.34 or later (Ubuntu 22.04, Debian 12, RHEL 9 and later releases), and the release build checks it; it needed glibc 2.38

### Packages

- The macOS and Windows packages hold THIRD_PARTY_LICENSES.txt, each library and data set they carry with its version, licence, home page and source, followed by the licence texts; they held none

### Quitting

- Ctrl+Q, the window's close button and the application menu's Quit end VX once the window has closed, its size saved; they closed the window and left VX to end by itself, which work always waiting on its main loop could have prevented, leaving it running with no window

---

## v0.9.0.1: 2026-05-16 (archival re-publish)

Metadata-only release. No changes to binaries or APIs since
v0.9.0. This tag exists so that the public-facing repository is
captured in a Zenodo deposit and assigned a citable DOI for the
accompanying manuscript. README polish, per-path commit-message
tidy-up, and topic-tag listing committed since v0.9.0 are included
in the archived snapshot.

---

## v0.9.0 "Aardvark": 2026-05-14 (first public pre-release)

First public-facing release. Triple-platform binaries (Linux,
macOS arm64, Windows x86_64) packaged from a single source tree.

### Added

- **Load-status strip**: a persistent UI strip showing file-open
  progress (parse phase) and per-region read-fetch progress. The
  strip never leaves the user wondering whether VX is busy or
  frozen.
- **Subsampling badge**: alignment tracks now overlay a small
  badge whenever the on-screen read set has been subsampled
  (capped by `max_reads`, default 500) so the user knows whether
  what they see is the full picture.
- **Asynchronous BAM loading**: region fetches no longer block
  the render thread. The viewport stays interactive while reads
  load in the background.
- **Analysis framework (Phases 1 to 4)**: 50+ computational
  analyses across signal math, sequence, quantification,
  interval operations, variant analysis, alignment stats, peak
  detection, interaction analysis, and cross-track correlation.
  Results land in a configurable `Results/` directory or, where
  appropriate, as a brand-new track.
- **Video recording**: capture the OpenGL viewport to MP4
  (H.264), WebM (VP9), or GIF. Configurable fps and capture
  mode (timer or per-frame). Uses ffmpeg via a piped raw-frame
  channel and PBO-backed GL readback.
- **MCP catalogue (43 tools)**: exposed via `mcp/vx_mcp_server.py`
  and reachable directly over HTTP on `127.0.0.1:9876`. Covers
  observation, navigation, file loading, track management,
  group management, data queries, export, bookmarks, loading
  status, runtime configuration, analysis dispatch, video
  recording, and per-track-type display options.
- **Magnifier popup**: Alt + hover over the viewport to open a
  rounded magnified inset (1.5× to 10×).
- **Active mode**: Click any rendered element (gene, exon,
  read, variant, signal bin) to surface metadata in a
  pinnable side panel.
- **Bookmarks**: Name + revisit specific regions; persisted in
  the session file.
- **Sessions**: Save/load full UI + track state to a `.vxs`
  JSON file.
- **Triple-platform release profiles**:
  - Linux: `release-aggressive` (x86-64-v3 baseline),
    `release-znver2` (AMD Zen2), `release-broadwell`
    (Intel Broadwell), `release-native` (build-host CPU).
  - macOS: arm64 `.app` + `.dmg`, ad-hoc signed, relocatable.
  - Windows: x86_64 ZIP + Inno Setup `.exe` installer.

### Changed

- Release builds now use full LTO + static druntime/phobos
  on Linux. The narrowed `gtk-d:gtkd` dependency drops unused
  peas/vte/gstreamer/sv subpackages that previously caused a
  `libpeas-1.0.so.0` runtime-dlopen() to fail on hosts that
  only ship `libpeas-1.0.so.1`.
- All release-profile binaries are ≤ 19 MB on Linux.

### Known limitations

- **First-region BAM fetch on very large BAMs** (≈ 23 GB) may
  take ~2 minutes the first time you navigate into a chromosome.
  The load-status strip surfaces this; the underlying root-cause
  fix is deferred. Subsequent regions on the same chromosome are
  fast.
- **macOS GUI smoke test on real Apple Silicon hardware**: the
  binary builds, the HTTP API has been confirmed, but full-GUI
  visual confirmation on a real M1/M2/M3 Mac is pending. (The
  available CI VM tier uses a software OpenGL renderer that
  cannot compile our GLSL 130/330 shaders.)
- **Subsampling cap**: when more than 500 reads (default) fall in
  the visible window, only a uniform subsample is shown. Increase
  `max_reads` via the alignment-track options panel or the
  `vx_set_alignment_options` MCP tool to see more.

### Not included

- Source code. The VX D source remains proprietary; this
  repository ships only the redistributable artefacts. See the
  [main README](README.md) for the per-folder licensing matrix.

---

## Pre-public history

v0.9.0 is the first version exposed to the public, but it
inherits roughly 18 months of internal iteration. The pre-public
development history is maintained in private issue trackers and
is not included in this changelog. Selected highlights of recent
work that shapes the v0.9.0 user experience:

- **2026-05-14**: Release-profile unification: full LTO with
  static druntime/phobos, narrowed gtk-d subpackage dependency.
- **2026-05-14**: Load-status strip + subsampling badge landed.
  macOS bundle rebuilt for the unified release profile.
- **2026-05-13**: Async BAM loading: render thread no longer
  blocks on region fetches.
- **2026-05-13**: Read sort + CIGAR coverage optimisation for
  very large alignment regions.
- **2026-04-25**: Background-analysis status bar,
  drag-and-drop track reorder, borderless-window edge-resize fix.

---

## Citation

If you use VX in research, please see the citation block in the
[main README](README.md). DOI to follow on manuscript
publication.

