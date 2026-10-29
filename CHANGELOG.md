# Dirt Gear releases

## v1.0.1 — 2026-10-29

Speed and shading fixes.

- **Much faster editing.** The on-screen preview now uses a fast renderer: psd-tools' own blend maths run at screen resolution on cached layer data, spread across all CPU cores. On a heavy 4K / 70-layer test PSD: layer toggle ~80 s → ~3 s, logo/name move ~80 s → under 1 s, first preview ~80 s → ~11–20 s (measured on a slow 2-core machine; faster on a normal PC).
- **Layer toggles no longer freeze the app.** Rows update instantly; several clicks are batched into one preview update, with "Updating preview…" in the status bar instead of a blocking dialog.
- **Moving artwork re-blends only what's above it.** The composite beneath your artwork is cached, so drags update in well under a second.
- **Artwork under shading:** shading detection now handles combined groups such as "SHADING/NORM" (artwork goes below the whole group) and names like wrinkles/folds/AO/highlights. If no shading is found, Dirt Gear says so and highlights the "Your added layers" strip to drag.
- Layer thumbnails load after the preview, two at a time, reuse the preview's decoded layers, and are cached by the browser.
- 3D preview uses the fast renderer for the diffuse texture.
- Unchanged: exports and "Check final rendering" still use the exact full-resolution psd-tools composite. PSDs using features the fast renderer can't reproduce (layer strokes, pattern/gradient overlays, vector-drawn masks/fills, knockout) automatically fall back to the exact renderer.

## v1.0 — 2026-10-29

Dirt Gear is the successor to Moto Gear v1.3, rebuilt with a new look. Same engine, same game-ready exports.

- New dark workshop interface: cleaner top bar with the open template shown as a pill, segmented Diffuse/Norm/Spec switch, slimmer status bar and a calmer canvas backdrop.
- Layers panel redesigned: larger thumbnails, eye/lock icons instead of checkboxes, role tags (SHADE / NORM / SPEC / ART) and a clearly highlighted "Your added layers" section.
- Right panel reorganised into cards: Add (logo, paste, name, number, saved logos, layouts), Selected artwork, Saved colours. Finish & ride is pinned to the bottom so Pack & install is always one click away.
- Redesigned dialogs (text, 3D preview, saved logos, layouts) with live font preview up top and toggle switches.
- New Dirt Gear icon and wordmark.
- Projects now save as `.dirtgear`. Old `.motogear` files still open, and still show under Continue last project.
- On first launch, Dirt Gear copies your Moto Gear saved projects, logos and layouts into its own library (`%LOCALAPPDATA%\Dirt Gear`). The Moto Gear folder is left untouched.
- Portable PyInstaller spec and one-step `build\build.ps1` (no hard-coded paths from the old workspace).
- Unchanged: PSD handling, under-shading compositing, text rendering, 3D viewer, PNT packer, and the export contract (rider.tga 24-bit RGB; rider_n/rider_r 32-bit with every alpha byte 0).

---

Moto Gear history (predecessor):

## v1.3 — 2026-10-23

- Save all added logos, names and numbers as a reusable Logo layout. Apply to another gear PSD with editable layers, proportional positions/sizes, rotation, opacity, colours and order preserved.
- Layouts retain text/gradient settings and saved colours; target template shading/Normal/Spec selections stay intact. Matching UV layouts give the best results.
- Saved colour swatches are available independently for each gradient stop. Applied gradient colours are added to the saved palette.
- Distributed as one self-contained Windows installer EXE, with model, fonts and Python runtime included.

## v1.2 — 2026-10-07

- Delete saved logos directly from the library, with confirmation. Copies already imported into projects remain intact.
- 3D viewer uses the PSD Normal map for surface detail and Reflection map RGB for studio highlights/reflections. Both effects can be toggled independently.
- Pitch-black 3D backdrop; existing zoom, rotation and pan controls retained.
- UV tangent frames added to the rider mesh, with correct handedness for mirrored UVs.
- Viewer maps loaded at up to 4096px and cached. Missing Normal maps use a flat normal; missing Reflection maps use black (matte).
- Export formats and pitch-black Norm/Spec alpha are unchanged. Preview lighting approximates a studio and is not the MX Bikes engine shader.

## v1.1.1 — 2026-10-04

- 3D panning with Shift-drag, right/middle-drag, a Pan-mode button, and up/down buttons. Reset restores the centred view and zoom.
- Detect dedicated Norm/Spec groups instead of combined shading/map containers; exclude nested shading/spec branches from Normal detection.
- Remove the arbitrary 64-Normal-layer limit while validating all selected layers.
- Verified the reported 2026 FOX FLEXAIR DNGR ST LOUIS BY RC PSD opens and exports black-alpha Norm/Spec textures.

## v1.1 — 2026-10-04

- Offline 3D gear viewer using the supplied WBD rider model and original paint UVs; rotate, zoom, front/back and reset controls.
- Gradient names/numbers with two colour stops, six directions, live font preview and full-resolution gear eyedroppers.
- Local saved-logo library for reusing artwork in other projects.
- Coalesced screen redraws, bounded decoded-pixel cache, faster preview PNG encoding, and affected-region compositing for compatible PSDs. Exports retain original resolution.
- Measured one rotated-logo update on the real 4096px Fox PSD at 1.13 seconds versus 8.38 seconds for the full render; identical pixels. This is a specific test, not a guarantee for every PSD.

## v1.0 — 2026-10-03

First named release, based on the tested font-preview build. Includes PSD gear editing, logos, names and numbers, live font preview, artwork placement under shading, editable project saving, bundled BYD/MX fonts, and MX Bikes PNT export with black Norm/Spec alpha.

Future fixes use v1.0.1, v1.0.2, etc. Feature updates use v1.1, v1.2, etc.
