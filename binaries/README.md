# VX: Pre-compiled binaries

The binary archives are **not committed to this Git repository**. They are attached to each tagged release under the
[Releases](https://github.com/Arnaroo/VX/releases) tab, so the repository stays small.

This README explains what each release asset is, how to verify it, and how to install and run it.

**Licence:** CC-BY-NC-ND-4.0, see [`../LICENSE-binaries.txt`](../LICENSE-binaries.txt). The libraries the macOS and
Windows packages carry keep their own licences: see *What's bundled* below.

---

## Asset matrix (v0.10.0)

| Platform | Asset | Format | Size |
|---|---|---|---|
| Linux x86_64 (x86-64-v3: Intel Haswell or AMD Excavator and later; glibc 2.34 or later) | `VX-0.10.0-linux-x86_64.tar.gz` | Tarball | 8.1 MB |
| macOS arm64 (Apple silicon, macOS 26 or later) | `VX-0.10.0-macos-arm64.dmg` | Disk image | 22.9 MB |
| Windows x86_64 (Windows 10 or 11; x86-64-v3, as for Linux) | `VX-0.10.0-windows-x86_64.zip` | ZIP | 58.6 MB |

Each asset has a `.sha256` file beside it holding its SHA-256 digest. The demo datasets are separate assets, under the
`demo-data-v1` release; VX downloads them itself (Open > Open Demo Dataset).

---

## Verifying the download

Check the digest before running a program downloaded from the internet.

### Linux

```bash
sha256sum -c VX-0.10.0-linux-x86_64.tar.gz.sha256
```

### macOS

```bash
shasum -a 256 -c VX-0.10.0-macos-arm64.dmg.sha256
```

### Windows (PowerShell)

```powershell
Get-FileHash -Algorithm SHA256 VX-0.10.0-windows-x86_64.zip
# Compare with the digest in VX-0.10.0-windows-x86_64.zip.sha256.
```

A digest that does not match means the download is damaged or was altered: do not run it. Download it again from the
GitHub Releases page.

---

## Installing

### Linux

```bash
tar xzf VX-0.10.0-linux-x86_64.tar.gz
./VX-0.10.0-linux-x86_64/bin/vx
```

The tarball holds VX, the font it draws with and its documents (README-INSTALL.txt says what is where). VX uses the
distribution's GTK 3, FreeType and OpenGL driver, which most desktops have; otherwise:

- Debian, Ubuntu: `sudo apt install libgtk-3-0 libfreetype6 libgl1`
- Fedora: `sudo dnf install gtk3 freetype mesa-libGL`
- Arch: `sudo pacman -S gtk3 freetype2 libglvnd`

fontconfig (the system's fonts), libcurl (downloads: the demo datasets, Retrieve Reference) and ffmpeg (video
recording) are used when present. The build needs an x86-64-v3 processor; on an older one it stops at once with
"Illegal instruction". It also needs glibc 2.34 or later (Ubuntu 22.04, Debian 12, RHEL 9, Fedora 35 and later releases).

### macOS

Open the `.dmg`, drag **VX.app** to Applications and eject the image. The application is ad-hoc signed, not notarised:
at the first start macOS refuses it once. Open System Settings > Privacy & Security, choose **Open Anyway** beside VX's
entry, and confirm (the image's README.txt says the same, and gives the Terminal command that removes the quarantine
instead). The bundle runs from any folder.

### Windows

Extract the ZIP anywhere and run `vx.exe` in the extracted `vx-windows` folder. Nothing is installed system-wide.
`vx-console.exe` beside it is the same program for a terminal: the command line, `--headless` and `--analysis`, whose
answer it prints.
Windows SmartScreen may warn at the first start (the program is not signed): choose *More info*, then *Run anyway*.

---

## What's bundled

| Platform | Bundled |
|---|---|
| Linux | VX and its font (DejaVu Sans Mono, with its licence); GTK 3 and the other libraries come from the distribution |
| macOS | GTK 3 and the libraries it uses (35 libraries, Homebrew's builds for macOS 26), GTK's schemas, the Adwaita and hicolor icon themes, fontconfig's configuration, the font |
| Windows | GTK 3 and the libraries it uses, libcurl with OpenSSL (53 DLLs, MSYS2's MINGW64 builds; libtiff built for VX without JBIG), the PNG, JPEG and SVG image loaders, GTK's schemas, the Adwaita and hicolor icon themes, fontconfig's configuration, the font |

The macOS and Windows packages hold `THIRD_PARTY_LICENSES.txt`: every library and data set they carry, with its version,
licence, home page and source, followed by the licence texts. VX is based in part on works of the GtkD project
(http://gtkd.org); the one change VX's build makes to GtkD is published in [`../third_party/GTKD.md`](../third_party/GTKD.md).

---

## Build provenance

How each binary was produced (toolchain versions, compiler flags, build hosts) is in
[`../docs/BUILD_PROVENANCE.md`](../docs/BUILD_PROVENANCE.md). In short: LDC 1.43.0 with full LTO and the D runtime
linked statically on Linux; LDC 1.41.0 at -O3, without LTO, with the static D runtime force-loaded on macOS; LDC 1.43.0
with the MSVC linker and full LTO on Windows.

---

## Reporting issues with a specific binary

Please include:

- the exact file name and version of the binary you downloaded;
- its SHA-256 digest (so that we can confirm which build it is);
- the operating system and its version;
- the log of the run: VX writes one file per run in `~/.local/state/vx/` on Linux, `~/Library/Logs/VX/` on macOS and
  `%LOCALAPPDATA%\VX\logs\` on Windows. For more detail, start VX with `VX_VERBOSITY=t3l3` set in the environment.

See [`../docs/TROUBLESHOOTING.md`](../docs/TROUBLESHOOTING.md) for more.
