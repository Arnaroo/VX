# Build provenance

This document records how each pre-compiled VX Genome Viewer binary
attached to a GitHub release is produced. It exists so a downstream
auditor can answer three questions without access to our build hosts:

1. **What compiler and flags built each binary?**
2. **Which third-party libraries are bundled, and where did they
   come from?**
3. **What can be verified after the fact (sizes, hashes, smoke
   tests)?**

It is a distilled, public-facing summary of the internal build
notes — host-specific paths and provisioning credentials have been
stripped.

The D source code that produced these binaries is **proprietary and
confidential** and is not distributed through this repository
(see the per-folder license matrix in the top-level
[`README.md`](../README.md)).

---

## Common ground

All platforms share the same source tree, the same DUB package
description (`dub.json`), and the LDC LLVM-based D compiler.
Release builds always set the following flags:

| Flag                                | Effect                                            |
|---|---|
| `-O3`                               | Highest optimisation level                        |
| `--fp-contract=fast`                | Fuse floating-point ops where safe                |
| `-boundscheck=off`                  | Drop array-bounds checks (release-only)           |
| `-flto=full`                        | Full link-time optimisation                       |
| `--link-defaultlib-shared=false`    | Static druntime + Phobos                          |
| `-defaultlib=phobos2-ldc-lto,druntime-ldc-lto` | LTO-instrumented stdlib   |
| `-function-sections` / `-data-sections` + `--gc-sections` | Dead-code/data elimination |
| `--as-needed`                       | Drop unreferenced DT_NEEDED entries               |
| `-fuse-ld=lld`                      | LLD for fast LTO link                             |
| `releaseMode`, `optimize`, `inline`, `noBoundsCheck` (DUB)    | Release semantics |

Profiles differ only in the CPU target (`-mcpu`/`-mattr`).

---

## Linux

| Item                | Value                                                              |
|---|---|
| Host triple         | `x86_64-pc-linux-gnu`                                              |
| Toolchain           | LDC 1.42+ with LLVM 19 (Manjaro/Arch packages)                     |
| Linker              | `lld` (via `-fuse-ld=lld`)                                         |
| Runtime libc        | glibc on the build host (Linux release binaries dynamic-link libc) |
| GTK linkage         | dynamic — system GTK 3.24 expected at runtime                      |
| gtk-d dependency    | narrowed to `gtk-d:gtkd` subpackage (drops peas/vte/gstreamer/sv)  |

### Build profiles

| Profile               | CPU target  | Intended audience              | Approx. size |
|---|---|---|---|
| `release-aggressive`  | `x86-64-v3` | Broad-compat x86-64 (≥ Haswell / Excavator) | ~19 MB |
| `release-znver2`      | `znver2` + AVX2/FMA/BMI2 | AMD Zen 2 (Ryzen 3000, EPYC Rome)         | ~19 MB |
| `release-broadwell`   | `broadwell` + AVX2/FMA/BMI2/RDSEED | Intel Broadwell and newer        | ~19 MB |
| `release-native`      | `native` (`-mcpu=native`) | Build-host CPU only — **NEVER SHIPPED**   | ~19 MB |

Build invocation (per profile `P`):

```bash
dub build --config=linux --build=P
```

The narrowed gtk-d dependency removes a stray `libpeas-1.0.so.0`
`dlopen()` that previously crashed the release binary on hosts that
only have `libpeas-1.0.so.1`.

### Bundled libraries (Linux)

None. The Linux binary expects a baseline GTK 3.24 + GLib + Cairo +
Pango + freetype + libepoxy install on the host. Distributions ship
these as part of the desktop. The release tarball does include the
binary's launch wrapper plus `genome-viewer.cfg` and the help
README.

---

## macOS

| Item                | Value                                                  |
|---|---|
| Host triple         | `arm64-apple-macos13.0`                                |
| Toolchain           | LDC **1.41.0** (pinned)                                |
| Linker              | Apple `ld`                                             |
| Runtime libc        | libSystem on macOS 13+                                 |
| GTK linkage         | bundled via `dylibbundler` (~30 dylibs)                |
| Bundle layout       | relocatable `vx-macos/{bin,lib}` + `VX.app` bundle      |

### Build pipeline (per `scripts/package_macos.sh`)

1. `dub build --config=linux` (note: `linux` config name is reused
   on macOS; only the platform-conditional source paths differ).
2. Copy `genome-viewer` into `vx-macos/bin/`.
3. Seed `vx-macos/lib/` with the GTK dylib roster that `gtk-d`
   resolves via `dlopen()` (15 dylibs:
   `libgtk-3.0.dylib`, `libgdk-3.0.dylib`, `libgobject-2.0.dylib`,
   `libgio-2.0.dylib`, `libglib-2.0.dylib`, `libgmodule-2.0.dylib`,
   `libgthread-2.0.dylib`, `libatk-1.0.dylib`,
   `libgdk_pixbuf-2.0.dylib`, `libcairo.dylib`,
   `libpango-1.0.dylib`, `libpangocairo-1.0.dylib`,
   `libharfbuzz.dylib`, `libfribidi.dylib`, `libepoxy.dylib`).
4. `dylibbundler -of -b -d lib/ -p @executable_path/../lib/`
   walks the transitive dependency graph from Homebrew
   (`/opt/homebrew`) and rewrites install names to be
   bundle-relative.
5. Build the native Mach-O launcher
   (`scripts/applauncher.c`) targeting `-arch arm64`,
   `-mmacosx-version-min=13.0`. The launcher sets
   `GDK_BACKEND=quartz,*` and `exec()`s `genome-viewer`.
   (A shell-script launcher is rejected by macOS Tahoe 15+
   Gatekeeper with error `-10669`.)
6. Assemble `VX.app/Contents/{MacOS,Resources}/`, write the
   `Info.plist` (bundle id `org.biocodecs.vx`, version `0.9.0`,
   `LSMinimumSystemVersion=13.0`).
7. Ad-hoc sign: `codesign --force --deep --sign - VX.app`.
8. Package the `.dmg`: `hdiutil create -volname … -format UDZO
   -fs HFS+`.

`scripts/package_macos.sh` also stages `LICENSE.txt`
(the CC-BY-NC-ND-4.0 text) into the bundle root, the `.app`'s
`Contents/Resources/`, and the DMG window.

### Bundled libraries (macOS)

| Source                                  | Count |
|---|---|
| Homebrew (`/opt/homebrew`) — GTK 3, GLib, Cairo, Pango, etc. | ~30 dylibs |
| Static druntime + Phobos                | linked into the binary itself |

Total `.app` bundle size: ~45 MB (binary + dylibs + icons).

Gatekeeper note: the bundle is ad-hoc signed only — first launch
requires right-click → Open (one-time confirmation). No Developer
ID signing or notarisation is performed.

---

## Windows

| Item                | Value                                                  |
|---|---|
| Host triple         | `x86_64-pc-windows-msvc`                               |
| Toolchain           | LDC matching the Linux pin, MSVC linker (VS 2022 Build Tools) |
| C runtime           | MSVC UCRT                                              |
| GTK linkage         | bundled via MSYS2/MINGW64 DLLs (~50 DLLs)              |

### Build pipeline

1. Run `scripts/build_windows.bat` from a VS 2022 *x64 Native
   Tools* command prompt — produces `bin/genome-viewer.exe`
   linked against the MSVC C runtime.
2. From an MSYS2 MINGW64 shell, run
   `scripts/package-windows.sh [--zip] [--installer]`. This:
   - copies the exe into `dist/vx-windows/`;
   - resolves every transitive MinGW64 DLL dependency by walking
     `ldd` and seeding the resolver with the GTK runtime DLLs
     that `gtk-d` `LoadLibrary`s at runtime (so they would
     otherwise be invisible to `ldd` on the exe alone);
   - copies all GdkPixbuf image-loader DLLs and rewrites
     `loaders.cache` to bundle-relative paths;
   - copies the GTK *Default* and *MS-Windows* themes plus the
     *Adwaita* and *hicolor* icon themes;
   - compiles the GLib schemas with `glib-compile-schemas`;
   - stages `LICENSE.txt` (CC-BY-NC-ND-4.0) at the bundle root.
3. With `--zip`, produces
   `dist/vx-{VERSION}-windows-x86_64.zip`.
4. With `--installer` and Inno Setup 6 (`iscc.exe`) on PATH,
   produces
   `dist/VX-{VERSION}-windows-x86_64-setup.exe` per
   `installer/vx-installer.iss`.

### Bundled libraries (Windows)

| Source                                            | Count    |
|---|---|
| MSYS2 MINGW64 (`/mingw64/bin/*.dll`) — GTK 3, GLib, Cairo, Pango, libepoxy, libpng, libjpeg, librsvg, harfbuzz, freetype, etc. | ~50 DLLs |
| GdkPixbuf image loaders (`lib/gdk-pixbuf-2.0/`)   | included |
| GTK themes (`share/themes/{Default,MS-Windows}`)  | included |
| Icon themes (`share/icons/{Adwaita,hicolor}`)     | included |
| GLib schemas (`share/glib-2.0/schemas/`)          | compiled |

Inno Setup compresses the bundle with `lzma2/ultra64` and produces
a per-user installer (no UAC prompt). Total installer size after
compression: ~20-25 MB.

---

## Verification (downstream)

For every release asset, the GitHub release page exposes:

- `vx-{VERSION}-linux-x86_64.tar.gz` + `.sha256`
- `VX-{VERSION}-macos-arm64.dmg` + `.sha256`
- `vx-{VERSION}-windows-x86_64.zip` + `.sha256`
- `VX-{VERSION}-windows-x86_64-setup.exe` + `.sha256`

Recommended downstream checks:

1. **Hash verification.** Compute `sha256sum <asset>` and compare
   against the matching `.sha256` file. Reject the binary on
   mismatch.
2. **HTTP-API smoke test.** Launch the binary; from another
   terminal run `curl -s http://127.0.0.1:9876/ping`. A response
   of `{"pong": true, …}` indicates the embedded HTTP server has
   started, which exercises the full process bring-up (DUB
   linkage, runtime init, GTK initialisation, OpenGL probe).
3. **Bundle-license presence.** Each release artefact embeds
   `LICENSE.txt` (CC-BY-NC-ND-4.0) at its root (or under
   `Contents/Resources/` for the `.app`).
4. **Bundle-content audit.** For the Windows ZIP and macOS DMG,
   `unzip -l` / `hdiutil attach … && ls -R` should match the
   roster declared above (±a few patch-level DLL bumps).

Any deviation between an asset on the release page and this
provenance document should be reported via the public issues
tracker.

---

## Versioning

The published version on each release page (`{VERSION}` above)
matches the `version` field in the source-tree `dub.json`. There
is no separate build number — successive rebuilds of the same
source revision produce binaries with the same version string.
For development snapshots, the binary always identifies itself as
the `version` declared at the time of build, with no extra
`+gitsha` qualifier.

The first public release is `0.9.0` ("Aardvark"). See
[`../CHANGELOG.md`](../CHANGELOG.md) for the release timeline.
