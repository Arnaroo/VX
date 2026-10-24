# Build provenance

This document records how each pre-compiled VX binary
attached to a GitHub release is produced. It exists so a downstream
auditor can answer three questions without access to our build hosts:

1. **What compiler and flags built each binary?**
2. **Which third-party libraries are bundled, and where did they
   come from?**
3. **What can be verified after the fact (sizes, hashes, smoke
   tests)?**

It is a distilled, public-facing summary of the internal build
notes: host-specific paths and provisioning credentials have been
stripped. It describes VX 0.11.0 ("Callistemon").

The D source code that produced these binaries is **proprietary and
confidential** and is not distributed through this repository
(see the per-folder licence matrix in the top-level
[`README.md`](../README.md)).

---

## Common ground

All platforms share the same source tree, the same DUB package
description (`dub.json`) and the LDC compiler (the LLVM-based D
compiler). The D dependencies are GtkD 3.10.0 (its `gtk-d:gtkd`
subpackage alone, which drops the unused peas, vte, gstreamer and
sv subpackages), bindbc-opengl 1.0.5 and bindbc-loader 1.0.3. A
small C file that calls FreeType is compiled with the platform's C
compiler (gcc on Linux, clang on macOS, MSVC's `cl` on Windows).
VX's build changes GtkD in one place; the change is published in
[`../third_party/GTKD.md`](../third_party/GTKD.md).

Every release build sets DUB's `releaseMode`, `optimize`, `inline`
and `noBoundsCheck`, and these LDC flags:

| Flag | Linux | macOS | Windows | Effect |
|---|---|---|---|---|
| `-O3` | yes | yes | yes | Highest optimisation level |
| `--fp-contract=fast` | yes | yes | yes | Fuse floating-point operations where possible |
| `-boundscheck=off` | yes | yes | yes | No array bounds checks |
| `-mcpu=` | `x86-64-v3` | `apple-m1` | `x86-64-v3` | The processor the code is built for |
| `-flto=full` with `-defaultlib=phobos2-ldc-lto,druntime-ldc-lto` | yes | no | yes | Full link-time optimisation, the D runtime and Phobos included |
| `--link-defaultlib-shared=false` | yes | no (the static libraries are force-loaded instead, see below) | yes | The D runtime and Phobos linked statically |
| `-function-sections`, `-data-sections` | yes | no | yes | One section a function or datum, for the linker to drop what is unused |
| Linker flags | `--gc-sections`, `--as-needed`, `-fuse-ld=lld` | `-dead_strip` | `/OPT:REF`, `/OPT:ICF` | Dead-code elimination |

---

## Linux

| Item | Value |
|---|---|
| Build host | x86-64, an Arch-based distribution (Manjaro) with glibc 2.44 |
| Toolchain | LDC 1.43.0 (D front end 2.113.0, LLVM 22.1.8), DUB 1.42.0 |
| Linker | LLD 22.1.8 (`-fuse-ld=lld`) |
| Build type | `release-aggressive` (`-mcpu=x86-64-v3`) |
| Shared libraries linked | exactly `ld-linux-x86-64.so.2`, `libc.so.6`, `libm.so.6`, `libgcc_s.so.1`, `libGL.so.1` and `libfreetype.so.6`; the release build checks the set and fails if it differs |
| Loaded at run time | GTK 3 and the libraries GtkD opens by name (GLib, GObject, GIO, GDK, Pango, cairo, ATK, gdk-pixbuf and the like), and, when present, fontconfig and libcurl |
| C library | the binary's newest glibc symbol version is `GLIBC_2.34`, so it needs glibc 2.34 or later: `fmod`, which glibc 2.38 gave a new symbol version, is bound to the version every x86-64 glibc has by a small C file of the Linux build (its result for finite arguments is the same), and the release build fails if any symbol needs a glibc newer than 2.34 |

Build, per release:

```bash
dub build --config=linux --build=release-aggressive --compiler=ldc2 --force
```

The binary is then checked (`--version` names the version and the
codename), its debug sections are stripped (`strip --strip-debug`;
the symbol table is kept, so that a crash report still names
functions), and it is staged with the font it draws with (DejaVu
Sans Mono and its licence) and a `SHA256SUMS`. The tarball holds one
directory, `VX-0.11.0-linux-x86_64/` (`bin/vx`, `fonts/`,
`README-INSTALL.txt`, `README.md`, `LICENSE.txt`, `SHA256SUMS`),
and is made reproducibly from the staged files: names sorted, owner
and group 0, every time set to the release date, gzip without a
name or a time.

`dub.json` also has the build types `release-znver2` (AMD Zen 2),
`release-broadwell` (Intel Broadwell), tuned builds of the same
source, and `release-native` (the build host's own processor,
never published). 0.11.0 publishes the `x86-64-v3` build alone.

### Bundled libraries (Linux)

None. GTK 3, FreeType and the OpenGL driver come from the
distribution (see the main README's install notes). The tarball
holds VX, its font and its documents.

---

## macOS

| Item | Value |
|---|---|
| Build host | an Apple silicon Mac running macOS 26 |
| Toolchain | LDC 1.41.0 (D front end 2.111.0, LLVM 20.1.5) |
| Linker | Apple's `ld` |
| Build type | `release-macos`: `-O3 -mcpu=apple-m1 --fp-contract=fast -boundscheck=off -dead_strip`, no LTO |
| D runtime | LDC's static `libdruntime-ldc.a` and `libphobos2-ldc.a`, force-loaded (`-force_load`) |
| Frameworks | OpenGL, CoreFoundation, CoreText |
| GTK | Homebrew's GTK 3.24.52 and the libraries it uses (Homebrew's builds for macOS 26), bundled |
| Lowest macOS | 26.0: the bundle's `LSMinimumSystemVersion` is the highest minimum of the binary and of every library it carries |

Packaging:

1. `dub build --config=macos --compiler=<LDC's ldc2> --build=release-macos`.
2. The GTK libraries GtkD opens by name, and every library they
   need, are copied from Homebrew with `dylibbundler`, which gives
   them `@rpath/` install names; the binary's run paths are
   `@executable_path/../Resources/lib` (VX.app) and
   `@executable_path/../lib` (the folder `vx-macos`). The packaging
   stops if any library refers to a file outside the bundle or the
   system.
3. GTK's data is added: the GSettings schemas (compiled), the
   hicolor and Adwaita icon themes, empty caches for gdk-pixbuf's
   loaders and GTK's input methods (the built-in ones are used), a
   fontconfig configuration, and the font with its licence.
4. `VX.app` is assembled: the binary is `Contents/MacOS/vx`, the
   rest under `Contents/Resources/`, with `Info.plist` (bundle id
   `org.biocodecs.vx`, version 0.11.0), `LICENSE.txt` and
   `THIRD_PARTY_LICENSES.txt`.
5. Ad-hoc signing: `codesign --force --deep --sign - VX.app`; the
   packaging stops unless `codesign --verify --deep --strict`
   accepts the bundle.
6. The disk image: `hdiutil create -format UDZO -fs HFS+`, holding
   `VX.app`, a link to Applications, `README.txt`, `LICENSE.txt`
   and `THIRD_PARTY_LICENSES.txt`; then its `.sha256`.

### Bundled libraries (macOS)

| Source | Count |
|---|---|
| Homebrew (`/opt/homebrew`): GTK 3, GLib, cairo, Pango, HarfBuzz, FreeType, fontconfig, gdk-pixbuf and what they need | 35 libraries |
| Static druntime + Phobos | linked into the binary itself |

`THIRD_PARTY_LICENSES.txt` names each Homebrew formula the bundle holds,
with its version, licence, home page and source, followed by the
licence texts.

Gatekeeper note: the bundle is ad-hoc signed only, with no
Developer ID signing and no notarisation. macOS refuses its first
start; System Settings > Privacy & Security > *Open Anyway* lets
it through, after which it opens at once.

---

## Windows

| Item | Value |
|---|---|
| Build host | Windows x86-64 |
| Toolchain | LDC 1.43.0 (its `windows-multilib` release) |
| Linker | LLD (`lld-link`), the linker built into LDC, which a full link-time optimisation needs; the C runtime, the Windows SDK's libraries and MSVC's `cl` (for a small FreeType shim) from the Visual Studio Build Tools 18.4 (MSVC 14.50) |
| Target | `x86_64-windows-msvc` |
| Build type | `release-windows`: `-O3 -mcpu=x86-64-v3 --fp-contract=fast -boundscheck=off -flto=full`, the LTO druntime and Phobos linked statically, `-function-sections -data-sections`, `/OPT:REF /OPT:ICF` |
| Configuration | both of `dub.json`'s: `windows-gui` (linked with `/SUBSYSTEM:WINDOWS`, no terminal window) as `vx.exe`, and `windows` (a console program, for the command line) as `vx-console.exe` |
| GTK | MSYS2's MINGW64 GTK 3.24.51 and the DLLs it needs |
| Other libraries | libcurl 8.21 from MSYS2 with OpenSSL 3.6; libtiff 4.7.1 built with MSVC without JBIG and without external codecs, so that the package holds no GPL library |

Packaging:

1. The DLLs: those `vx.exe` imports, the GTK libraries GtkD loads
   by name, libcurl, and the PNG, JPEG and SVG loaders of
   gdk-pixbuf, each with the DLLs it imports (read with MSVC's
   `dumpbin`). Every DLL must be on a fixed list of 53, each
   added only once its purpose and licence are known, or the
   packaging stops.
2. GTK's data: the loaders' cache cut to the three loaders, GTK's
   Default theme (its key bindings), the Adwaita and hicolor icon
   themes, the GSettings schemas (compiled), fontconfig's
   configuration, and the font with its licence.
3. `LICENSE.txt` and `THIRD_PARTY_LICENSES.txt` (each MSYS2
   package the ZIP holds, with its version, licence, home page and the
   source archive of the exact build, followed by the licence
   texts).
4. The ZIP, `VX-0.11.0-windows-x86_64.zip`, holding one folder,
   `vx-windows/`, and its `.sha256`. No installer is published.

### Bundled libraries (Windows)

| Source | Count |
|---|---|
| MSYS2 MINGW64: GTK 3, GLib, cairo, Pango, HarfBuzz, FreeType, fontconfig, gdk-pixbuf, libepoxy, libpng, libjpeg, librsvg, libcurl, OpenSSL and what they need; libtiff built for VX | at most 53 DLLs, each on the fixed list |
| gdk-pixbuf image loaders (`lib/gdk-pixbuf-2.0/`) | PNG, JPEG, SVG |
| GTK theme (`share/themes/Default`) | key bindings |
| Icon themes (`share/icons/{Adwaita,hicolor}`) | included |
| GSettings schemas (`share/glib-2.0/schemas/`) | compiled |
| fontconfig configuration (`etc/fonts/`) | included |

---

## Verification (downstream)

For every release asset, the GitHub release page exposes the asset
and its `.sha256`:

- `VX-{VERSION}-linux-x86_64.tar.gz` + `.sha256`
- `VX-{VERSION}-macos-arm64.dmg` + `.sha256`
- `VX-{VERSION}-windows-x86_64.zip` + `.sha256`

Recommended downstream checks:

1. **Hash verification.** Compute `sha256sum <asset>` and compare
   against the matching `.sha256` file. Reject the binary on
   mismatch. After unpacking the Linux tarball,
   `sha256sum -c SHA256SUMS` in its directory checks every file.
2. **Version.** `vx --version` prints the version, the codename
   and the build date, and exits.
3. **HTTP-API smoke test.** Launch the binary; from another
   terminal run `curl -s http://127.0.0.1:9876/ping`. The answer
   `{"status":"ok","app":"VX","api_version":2}` shows that the
   program started and its API server listens.
4. **Bundle-licence presence.** Each package holds `LICENSE.txt`
   (CC-BY-NC-ND-4.0): at the root of the Linux directory and of
   `vx-windows/`, in the disk image and in `VX.app`'s
   `Contents/Resources/`. The macOS and Windows packages hold
   `THIRD_PARTY_LICENSES.txt` beside it.
5. **Bundle-content audit.** `tar -tzf`, `unzip -l` or
   `hdiutil attach … && ls -R` should match the lists above; on
   Linux, `readelf -d bin/vx | grep NEEDED` lists the six libraries
   above.

Any deviation between an asset on the release page and this
provenance document should be reported via the public issues
tracker.

---

## Versioning

The published version on each release page (`{VERSION}` above)
is the version the binary reports (`vx --version`, and Settings >
About). There is no separate build number: successive rebuilds of
the same source revision report the same version and codename,
each with its own build date. For development snapshots, the
binary always identifies itself as the version declared at the
time of build, with no extra `+gitsha` qualifier.

The first public release is `0.9.0` ("Aardvark"); `0.9.0.1`
re-published it unchanged for its archival DOI, `0.10.0`
("Banksia") was the next version of the program, and `0.11.0`
("Callistemon") is the one after it. See
[`../CHANGELOG.md`](../CHANGELOG.md) for the release timeline.
