# Dirt Gear releases

## v1.0.6 — 2026-10-30

**Dirt Gear: everything new since Moto Gear v1.3**

**New look**
- Renamed to Dirt Gear, with a new logo and a cleaner dark interface.
- Layer eye/lock icons and SHADE / NORM / SPEC / ART tags. Finish & ride stays pinned at the bottom.

**Much faster**
- New fast preview renderer: layer toggles take about 1–3 s and logo/name moves under 1 s, where they used to take ~80 s on big 4K PSDs.
- Layer clicks no longer freeze the app. Rapid clicks are batched.
- Layer effects (pattern/colour/gradient overlays, strokes) stay fast.
- Exports and Check final rendering still use the exact full-quality render.

**Better results**
- Logos, names and numbers go under the shading on more PSDs, including combined "SHADING/NORM" groups. You get a warning if no shading layer is found.
- New **letter spacing** slider for names and numbers.

**Updates built in**
- Dirt Gear checks for new versions on launch: **Download and install**, **Skip this version**, or see What's new. Updates are signed and checked before installing.

**Fixes**
- Layers not switching off, or the canvas going blank or white, when toggling layers.
- Two-line text failing with newer Pillow versions.

**Kept from Moto Gear:** PSD colourways, logos/names/numbers, gradients, saved logos and layouts, 3D preview, .pnt/TGA export with black Norm/Spec alpha, and Pack & install into MX Bikes. Your Moto Gear projects, logos and layouts are copied across on first launch, and `.motogear` files still open.

## v1.0.5 — 2026-10-30

- **Letter spacing for names and numbers:** a new slider in the Add/Edit text dialog, from −50% (tighter) to +100% (wider), with live preview. The font's own kerning is kept, so a 6 still tucks under a 7, and spacing is applied on top. Outlines stay behind the letters even when they overlap. Gradients and two-line text work too. Double-click the slider to reset to 0%.
- Spacing is saved with the layer and kept by **Edit text**, saved projects and logo layouts.
- At 0% text renders exactly as before.
- Two-line text no longer fails with newer Pillow versions.

## v1.0.4 — 2026-10-30

Fixes for layers not switching off and the canvas going blank.

- **Layer effects in the fast preview:** colour, pattern and gradient overlays and strokes are drawn once at full quality, then cached. Before, one layer with a Pattern Overlay (e.g. "Calque 95" in the Fox 180 Draft PSD) sent the whole PSD back to the slow full-4K renderer, about 25 s per change. Clicks then piled up and layers looked stuck or the canvas went blank. On that PSD: first preview ~25 s → ~2 s, each toggle ~1 s.
- **Out-of-order requests are ignored:** each change carries a sequence number, so an older request can't switch back layers you've already changed.
- **Layers with no pixel data** (some smart objects) are treated as transparent, as psd-tools does. Before, switching one on could turn the whole preview white.
- Tip: colourway layers like Honda / Navy / Orange / Pink are each full-canvas, so only the top visible one shows. Turn the top one off to see the next.

## v1.0.3 — 2026-10-30

- First signed release: if you have v1.0.2, this arrives through **Download and install** in the app.
- Before publishing, the release build checks on Windows that an installed copy can update itself end to end.

## v1.0.2 — 2026-10-30

- **Built-in updates**, the same as Optic and Moto Lines Studio. Dirt Gear checks GitHub on start and shows a bar when a new version is out: **Download and install** (signature and SHA-256 checked, closes, updates in place, reopens), **Skip this version**, or dismiss. *What's new* shows the release notes.
- Click the version label (top left) for *About & updates*: check now, see what's new, and turn the start-up check on or off.
- Releases now publish `Dirt-Gear-Setup-<version>.exe` with a signed `update.json`. The workflow runs an end-to-end self-update test on Windows before publishing.
- The installer gained a silent update mode that waits for the app to close and rolls back on failure.
- Install this version once by hand. From here on, updates come through the app. See `docs/UPDATES.md` for the one-time signing key setup.

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
