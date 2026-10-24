# VX: Keyboard Shortcuts

Every shortcut below can be rebound in Settings (see
*Customising*). The defaults are the out-of-the-box bindings. On
macOS they use the Command key where this page says `Ctrl`
(Command-O, Command-Q), and Settings shows them as `Cmd+`;
shortcuts saved by an earlier version are read the same way.

---

## File

| Action | Default |
|---|---|
| Open a reference genome (FASTA) | `Ctrl+O` |
| Save session | `Ctrl+S` |
| Load session | `Ctrl+Shift+O` |
| Export snapshot (PNG, JPEG or TIFF) | `Ctrl+Shift+E` |
| Export SVG | `Ctrl+Shift+V` |
| Settings | `Ctrl+,` |
| Quit | `Ctrl+Q` |

## Navigation

| Action | Default |
|---|---|
| Pan left / right | `←` / `→` |
| Zoom in / out | `Ctrl++` / `Ctrl+-` |
| Zoom to fit (the whole chromosome) | `Ctrl+0` |
| Fit to window (the selection, else the largest gene or feature in view, else the chromosome) | `W` |
| Jump to start / end of chromosome | `Home` / `End` |
| Region search (puts the cursor in the search entry) | `Ctrl+F` |

## View

| Action | Default |
|---|---|
| Toggle grid lines | `Ctrl+G` |
| Toggle labels | `Ctrl+L` |
| Toggle left panel | `F9` |
| Toggle Active Mode | `Ctrl+I` |
| Toggle dark mode | `Ctrl+D` |

## Magnifier

| Action | Default |
|---|---|
| Show magnifier inset | Hold `Alt` while hovering |
| Increase magnification | `+` or `=` (while `Alt` is held) |
| Decrease magnification | `-` (while `Alt` is held) |
| Adjust magnification | `Alt` + scroll wheel |
| Keep the magnifier on without holding `Alt` (twice again lets it go; since 0.11.0) | Press `Alt` twice quickly (each press within 0.4 s of the last, nothing else pressed, clicked or scrolled meanwhile) |

## Bookmarks

| Action | Default |
|---|---|
| Add a bookmark of the view (nothing while no reference is loaded) | `Ctrl+B` |
| Next bookmark (of those Quick Navigation shows) | `Ctrl+]` |
| Previous bookmark (of those Quick Navigation shows) | `Ctrl+[` |

## Edit mode

| Action | Default |
|---|---|
| Cancel a drag that moves or resizes an item (with the Edit tab shown) | `Escape` |

## Recording

| Action | Default |
|---|---|
| Start / stop video recording | `Ctrl+Shift+R` |

## Mouse

| Action | Mouse |
|---|---|
| Pan | Scroll wheel, or drag |
| Zoom | `Ctrl` + scroll wheel (`Command` on macOS) |

The mouse actions, the magnifier's keys and `Escape` are fixed;
they are not rebound in Settings.

---

## Customising

Settings > Hotkeys lists the bindings by category (File,
Navigation, View, Bookmarks); *Export SVG* is set in Settings >
Output > Capture, whose shortcuts frame shows the same bindings
as the Hotkeys tab. Click a binding, then press the key
combination you want; `Escape` clears the binding instead.
*Reset All to Defaults* restores every binding.

Custom bindings are saved in `vx.cfg`, in its Hotkeys section, in
GTK's accelerator format: `<Primary>O`, where `<Primary>` is
Control, or Command on macOS.
