# VX Genome Viewer — Pre-compiled binaries

The actual binary archives are **not committed to this Git
repository**. They are attached to each tagged release under the
[Releases](https://github.com/Arnaroo/VX/releases) tab so the
repo stays small and clones stay fast.

This README explains what each release asset is, how to verify
it, and how to install/run.

**License:** CC-BY-NC-ND-4.0 — see
[`../LICENSE-binaries.txt`](../LICENSE-binaries.txt).

---

## Asset matrix

| Platform | Filename pattern | Format | Approx. size |
|---|---|---|---|
| Linux x86_64 (v3 baseline) | `VX-{version}-linux-x86_64.tar.gz` | Tarball | ~25 MB |
| macOS arm64 | `VX-{version}-macos-arm64.dmg` | Disk image | ~45 MB |
| Windows x86_64 (installer) | `VX-{version}-windows-x86_64-setup.exe` | Inno Setup installer | ~60 MB |
| Windows x86_64 (portable) | `VX-{version}-windows-x86_64.zip` | ZIP | ~55 MB |

Each asset is accompanied by a `.sha256` companion file
containing the SHA-256 digest.

---

## Verifying the download

Always verify the checksum before running an executable you
downloaded from the internet.

### Linux

```bash
sha256sum -c VX-X.Y.Z-linux-x86_64.tar.gz.sha256
```

### macOS

```bash
shasum -a 256 -c VX-X.Y.Z-macos-arm64.dmg.sha256
```

### Windows (PowerShell)

```powershell
Get-FileHash -Algorithm SHA256 VX-X.Y.Z-windows-x86_64-setup.exe
# Compare against the contents of the .sha256 file.
```

A mismatched hash means the download was corrupted or tampered
with — do not run it. Re-download from the GitHub Releases page
and try again.

---

## Installing

### Linux

```bash
tar xzf VX-X.Y.Z-linux-x86_64.tar.gz
cd VX-X.Y.Z-linux-x86_64
./bin/genome-viewer
```

The tarball is self-contained — it bundles GTK3, Cairo, Pango,
FreeType, fontconfig, GLib, and the rest of its non-glibc
dependencies. You need a glibc-based distro (Arch, Debian, Fedora,
Ubuntu, …) with a 4.x+ kernel.

### macOS

Open the `.dmg`, drag **VX.app** to `/Applications`, eject the
disk image. The first launch will prompt with Gatekeeper because
the build is **ad-hoc signed** rather than notarised — control-
click the app and choose "Open" once to whitelist it.

The `.app` bundle is relocatable: it can run from `~/Applications`
or a USB drive.

### Windows (installer)

Run `VX-X.Y.Z-windows-x86_64-setup.exe`. The installer is built
with Inno Setup; it places VX under `Program Files\VX`, creates a
Start Menu shortcut, and registers an uninstaller. Optional
checkboxes during install: desktop shortcut, "register VX as the
handler for `.vxs` session files".

### Windows (portable ZIP)

Extract anywhere and run `genome-viewer.exe` from the extracted
folder. The bundle is self-contained — no system-wide install
needed. Useful for USB-stick or shared-drive deployments.

---

## What's bundled

All three platforms ship with VX's non-baseline dependencies
included so the binaries run on a stock OS install of a recent
mainstream version.

| Platform | Bundled (high level) |
|---|---|
| Linux | GTK3, Cairo, Pango, FreeType, fontconfig, GLib, harfbuzz, atk, gdk-pixbuf, glib-schemas, default theme |
| macOS | ~30 dylibs (GTK3 stack + dependencies) via `dylibbundler`; `.app/Contents/Resources/` carries shaders, fonts, schemas |
| Windows | ~50 DLLs (MinGW64 GTK3 stack), GdkPixbuf loaders, GTK themes, GLib schemas, default font |

Per-library third-party license details are inside each archive's
`THIRD_PARTY_LICENSES.txt`.

---

## Build provenance

How each binary was produced — toolchain versions, compiler flags,
build-host description — is documented in
[`../docs/BUILD_PROVENANCE.md`](../docs/BUILD_PROVENANCE.md). The
short version: LDC + DUB with full LTO and static druntime+phobos
on Linux; LDC 1.41.0 with force-loaded static D runtime on macOS;
MSVC-linked LDC on Windows.

---

## Reporting issues with a specific binary

Please include:

- Exact filename + version of the binary you downloaded.
- SHA-256 hash (so we can confirm you got the right one).
- OS and OS version.
- The first ~50 lines of the diagnostic log produced by:

```bash
VX_DEBUG_GL=1 VX_DEBUG_ALIGNMENT=1 ./bin/genome-viewer 2>/tmp/vx_dbg.log
```

See [`../docs/TROUBLESHOOTING.md`](../docs/TROUBLESHOOTING.md)
for the full diagnostic playbook.
