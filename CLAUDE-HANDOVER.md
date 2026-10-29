# Dirt Gear — development handover

Prepared 29 October 2026. Version **1.0**: the successor to Moto Gear v1.3 with a full UI redesign and a new name.

## What changed from Moto Gear v1.3

The engine is Moto Gear v1.3's, kept deliberately: PSD handling, Norm/Spec detection, under-shading compositing, text rendering, layouts, the 3D viewer and the PNT packer are unchanged. Read `docs/moto-gear-v1.3-handover.md` for the full architecture, feature inventory, test history and owner preferences. All of it still applies.

**Frontend (rewritten look, same logic)**
- `source/static/index.html`: new structure (top bar with a doc pill, a card-based right panel, a pinned Finish & ride panel, an inline SVG icon sprite). **Every element ID from v1.3 is preserved**, so `app.js` logic is unchanged.
- `source/static/style.css`: new dark design system. Tokens are on `:root` (`--accent:#D7FF3C` fluoro lime, graphite panels). Layer visibility checkboxes are styled as eye, eye-off and lock icons through CSS masks. Other checkboxes are toggle switches.
- `source/static/brand.otf`: a copy of the bundled `MxFont - Racer.otf`, used for the wordmark.
- `source/static/icon.svg` and `source/icon.ico`: the new "D" mark.
- `app.js` edits: the `X-Dirt-Token`/`X-Dirt-Desktop` headers, the palette key `dirtGearPalette` (reads the old `motoGearPalette` as a fallback), a lime selection outline, `body.has-doc` and `body.pending` classes for status dots, and branding strings.
- `viewer.js`: the global was renamed `MotoRider` → `DirtRider`. The black backdrop is kept.

**Backend (`source/app.py`)**
- Branding strings, the temp prefix `dirt-gear-`, and the window title "Dirt Gear".
- The server accepts `X-Dirt-Token` **or** the legacy `X-Moto-Token`, so old test scripts still work.
- Data root is `%LOCALAPPDATA%\Dirt Gear\{Projects,Logos,Layouts}`. `migrate_moto_gear_library()` **copies** Moto Gear's library on first run, but only if the Dirt Gear folder doesn't exist yet, and writes `imported-from-moto-gear.txt`. It never modifies or deletes the Moto Gear folder.
- Projects save as `.dirtgear` (`PROJECT_EXT`). Recent and reopen also accept `.motogear`, and Open project accepts both, since the format is the same ZIP (version 1).
- The export contract is untouched.

**Build**
- `build/Dirt Gear.spec` uses `SPECPATH`-relative paths (no owner-machine absolute paths). Tkinter is excluded.
- `build/build.ps1` runs venv → app build → payload → single-file installer in one step. `build/installer.py` was rebranded (install dir `%LOCALAPPDATA%\Programs\Dirt Gear`, ctypes dialogs, no tkinter).

## Testing done for v1.0 (Linux sandbox, psd-tools 1.26)

Passed:
- A Playwright walkthrough at 1500×920 and 1100×760: start screen, open PSD, layer tree with thumbnails and role tags, add a name (live font preview), add a gradient number, artwork composited **beneath** a multiply shading layer in the shaded preview, selection and transform panel, Norm tab, and 3D preview rendering the current design. No page or console errors.
- Backend: the PNT exported and read back with 3 textures and the correct header name; in the TGA zip, `rider.tga` is RGB and `rider_n`/`rider_r` are RGBA with alpha extrema (0,0); `.dirtgear` quick-save, recent and reopen round-trip; `.motogear` portable open; and library migration from a Moto Gear folder.

Not done: a Windows build, the installer, the native pywebview window, the Windows clipboard, MX Bikes install-folder detection and in-game verification. These are Windows-only and must be checked on the owner's PC before giving the installer to friends. `requirements.txt` pins are unchanged from v1.3 (psd-tools 1.19.0). The sandbox used a newer psd-tools only for testing.

## Next steps

1. Run `build\build.ps1` on Windows. Clean-install into a test folder (`--quiet --no-shortcuts --target <dir>`) and launch.
2. Open a real 4K PSD (for example the Fox fixtures listed in the v1.3 handover), check under-shading, export, and test in game.
3. Version bumps: 1.0.x for fixes, 1.1 for features.
