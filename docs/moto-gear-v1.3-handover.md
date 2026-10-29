# Moto Gear — development handover for Claude

Prepared 29 October 2026. Current released version: **v1.3**, released 23 October 2026.

## Start here

You are continuing an existing Windows desktop application, not starting a replacement. Read the source and existing release notes before changing it. Preserve working PNT exports, zero alpha on Normal/Reflection exports, editable projects, bundled fonts and the user's saved libraries. The owner has confirmed that the current paint packing works in MX Bikes after earlier problems were fixed.

The purpose is to let people with little Photoshop experience personalise MX Bikes rider gear: open a creator's PSD, select colourways, add logos/names/numbers beneath shading, preview the result in 2D/3D, save an editable project and export a game-ready paint. The complicated Normal/Spec selection and alpha-saving steps are handled automatically.

This document describes the shipped implementation and previous test evidence. It is not a claim that all possible PSDs or Windows PCs work without issues. No application rebuild or new tests were performed just to create this handover.

## Files to give Claude

Workspace root on the owner's PC:
`C:\Users\frase\Documents\Codex\2026-09-22\do`

Paths below are relative to that root unless absolute:

| Path | Purpose |
| --- | --- |
| `outputs/Moto-Gear/source/` | Authoritative editable application source, static files, fonts, icon, requirements |
| `outputs/Moto-Gear/source/app.py` | Python backend, PSD handling, rendering, storage, desktop startup |
| `outputs/Moto-Gear/source/packing.py` | Independent TGA/PNT encoder and verification reader |
| `outputs/Moto-Gear/source/static/app.js` | Main editor UI and interaction/state logic |
| `outputs/Moto-Gear/source/static/index.html` | Editor controls/dialogs |
| `outputs/Moto-Gear/source/static/style.css` | Visual styling |
| `outputs/Moto-Gear/source/static/viewer.js` | Custom WebGL rider preview |
| `outputs/Moto-Gear/source/static/rider.json` | Converted rider mesh with UVs and tangent frames |
| `outputs/Moto-Gear/source/fonts/` | Bundled BYD/MX fonts (58 in the release) |
| `outputs/Moto-Gear/README.md` | User instructions, capabilities and limits |
| `outputs/Moto-Gear/CHANGELOG.md` | Release history |
| `outputs/Moto-Gear/VERSION.txt` | Current version: 1.3 |
| `outputs/Moto-Gear/THIRD_PARTY_NOTICES.txt` | Dependency notices |
| `outputs/Moto-Gear/release/TESTED.txt` | Actual v1.3 validation and limitations |
| `outputs/Moto-Gear/release/INSTALL.txt` | Installation/release information |
| `outputs/Moto-Gear/release/Moto Gear v1.3 Source.zip` | Existing release source snapshot |
| `outputs/Moto-Gear/release/Moto Gear v1.3 Setup.exe` | Friend-facing single installer |
| `outputs/Moto-Gear/app-v1.3/Moto Gear.exe` | Owner's current versioned application copy |
| `work/Moto Gear.spec` | PyInstaller application build specification |
| `work/release/build_payload.py` | Creates distributable payload ZIP |
| `work/release/installer.py` | Single-EXE Windows installer source |
| `work/test_*.py`, `work/test_*.cjs` | Existing development/regression tests; inspect individual assumptions |

Friend installer on Desktop:
`C:\Users\frase\OneDrive\Desktop\Moto Gear v1.3 Setup.exe`

The Desktop `.lnk` shortcut is not a distributable application. The installer includes the app and its resources; the installed application itself has an `_internal` directory which must stay beside its EXE. A remote Claude session cannot access these local paths unless the files are uploaded or the workspace is mounted. Provide the source, this document and the build/test scripts, not only the installer.

## User requirements and preferences

- Local Windows app; PSDs and editing stay on the user's computer. No account required.
- Simple interface suitable for non-designers, but retain access to creator colourways and diffuse layers.
- All PSD layers should appear in the left panel with thumbnails; smart objects remain single items, never expanded into their embedded contents.
- Added artwork must composite beneath the chosen shading layer/group in both final preview and exports.
- Default resizing preserves proportions; Shift allows stretching/narrowing. Independent text width is important.
- Crisp text at export resolution, exact reusable colours and gradients are important.
- People should never have to manually create black alpha channels for Norm/Spec.
- Use Moto Gear's own packer. PaintHub was supplied as a working reference, but the owner explicitly rejected integrating it.
- Friend distribution should be simple: one installer EXE, no Python installation.
- Continue version tracking: patch fixes can be 1.3.1; a feature release can be 1.4. Do not rename an old build as a new version without rebuilding.
- The owner dislikes repeated confirmations, generic-looking UI, slow editing and unnecessary rebuilds. Complete agreed changes and relevant checks together before packaging.

## Complete feature inventory

### PSD/template handling

- Supports 8-bit RGB PSDs up to 8192 x 8192; export uses source dimensions, not an automatic 4K conversion.
- Reads layer/group structure and initial visibility. User can hide intro overlays, old names/logos and select alternative colourways.
- Smart objects use their rendered appearance as single layers. Existing PSD text/smart objects are not directly editable as native text/vector objects.
- Automatic Normal and Spec detection. A multi-layer Normal group combines into one map for export.
- Detection prefers dedicated map groups and excludes shading/spec branches. A combined `SHADING/NORM` parent must not cause its whole subtree to become a Normal map.
- No arbitrary 64-Normal-layer limit remains.
- Missing Spec produces a full black RGB reflection map. Its exported alpha is also black.
- Map layers are protected for automatic export; ordinary design layers remain accessible.
- Default/Norm/Spec preview tabs; map previews are loaded on demand.
- Preview resolution increases on zoom, up to 4096 pixels. Full export retains original PSD resolution.

### Artwork and text

- Import PNG/JPG/SVG, drag files onto canvas, or Ctrl+V paste.
- Windows clipboard handling prefers SVG, then alpha-preserving PNG, then a bitmap. Illustrator native-only clipboard formats are not supported. SVG/PNG import is the fallback.
- SVG is rasterised on import, using PSD-scale resolution; it is not retained as an editable vector object.
- Optional Remove white background removes edge-connected white in flattened bitmap artwork.
- Add name/add number with font selection and live preview, colour, size and outline.
- Bundled BYD/MX fonts work without installing them in Windows; installed system fonts are also discovered.
- Added text retains settings for later Edit text & font and is rerasterised when enlarged rather than simply enlarging a tiny preview bitmap.
- Two-stop gradients with six directions, live preview and separate full-resolution gear eyedroppers.
- v1.3 allows saved swatches to select either gradient stop independently. Gradient colours are remembered in the palette.
- Move/resize/rotate, optional 15-degree rotation snapping; Shift permits free rotation when snapping is active.
- Resize proportionally normally; hold Shift for free stretch/narrow. Text width can change independently of height.
- Exact position, dimensions, rotation and opacity controls; tint artwork with a single colour.
- Scroll zoom, Alt-drag canvas pan, arrow-key nudge (Shift for larger steps), undo/redo using Ctrl+Z/Ctrl+Shift+Z.

### Layer placement and rendering

- Added logos/text are one movable section inside the PSD layer list.
- Drag the Your added layers heading onto a PSD layer to place the section below it.
- Reorder added artwork by dragging rows or using arrow buttons. The section shares one PSD insertion location; this is not arbitrary independent interleaving of every added layer throughout the PSD tree.
- Show artwork immediately at chosen opacity during manipulation/pending rendering. Final shaded rendering replaces that temporary editing preview.
- Footer distinguishes editing preview from final shaded result; Retry shading and Check final rendering are available.
- Preserve this distinction: immediate overlay visibility is not proof of final shading correctness. Test actual compositing under non-normal blend modes/groups.

### Persistence and reuse

- Save for later stores an editable project in the local library. Start screen can Continue last project.
- Save portable project creates `.motogear`, containing source PSD, artwork assets and state; open on another PC.
- Original source PSD is not modified.
- Saved logos library lets users reuse an individual added logo across projects.
- Delete saved logo asks for confirmation and removes only that library entry. Copies already imported in a project remain independent.
- v1.3 Logo layouts save all added names/numbers/logos as a named set, including text/gradient settings, palette, visibility, opacity, rotation and order.
- Applying a layout appends fresh independent artwork/assets to the target project. Positions/width scale by target/source width; positions/height scale by target/source height.
- Target PSD shading/Normal/Spec selections stay intact. One frontend undo step removes an applied layout.
- Delete saved layout removes its saved entry, not artwork already applied elsewhere.
- Layouts transfer added artwork, not baked-in/template PSD designs. Matching UV layouts work best; different UV layouts still require manual placement checks.

### 3D preview

- Custom offline WebGL viewer, not a hosted viewer or Blender runtime.
- Uses supplied WBD rider mesh and original paint UV layout.
- Rotate, zoom, Front/Back, Reset; Shift/right/middle drag pan, Pan mode and up/down buttons let the user inspect chest/legs when zoomed in.
- Black backdrop since v1.2.
- Uses current diffuse plus Normal and Reflection RGB, with separate Normal detail and Reflections toggles.
- Tangent-space normals, including tangent handedness for mirrored UVs; current mesh stride is 12.
- Procedural studio lighting/reflections approximate materials; not an exact recreation of the MX Bikes shader.
- Viewer uses RGB map data, ignoring export alpha zero. Missing Normal gets flat `(128,128,255)`; missing Reflection gets black/matte.
- Map textures capped at 4096px and cached with a bounded two-image cache.

### Export and game installation — preserve exactly

| Texture | Format | Alpha |
| --- | --- | --- |
| `rider.tga` | 24-bit RGB | None |
| `rider_n.tga` | 32-bit RGBA | Every byte 0 (pitch black) |
| `rider_r.tga` | 32-bit RGBA | Every byte 0 (pitch black) |

Zeroing alpha must preserve RGB. A missing Spec has black RGB as well as zero alpha. Do not interpret transparent-looking Norm/Spec thumbnails as absent RGB data.

- Export three TGAs as a ZIP or pack directly into `.pnt`.
- Native Save As dialog for portable exports. Internal PNT paint name is updated to the selected filename where handled by the save flow.
- Pack & install reads MX Bikes configured mods folder from `PiBoSo/MX Bikes/global.ini`, then selected rider model's paints folder (default model `default_mx`).
- User has confirmed current packing works. Earlier failures were real application defects, not grounds to repeatedly blame the user's folder selection.
- Revalidate any packer changes structurally and in-game; a structurally valid file alone does not establish in-game compatibility.

## Architecture and implementation

Python backend: Flask + Pillow + psd-tools composite + NumPy, with SciPy/scikit-image dependencies in the bundle. Desktop shell: pywebview using Microsoft Edge WebView2/EdgeChromium. Frontend: HTML/CSS/plain JavaScript, canvas editor and custom WebGL viewer.

Current direct requirements in `source/requirements.txt`:

```text
psd-tools[composite]==1.19.0
Flask==3.1.3
Pillow==12.3.0
numpy==2.5.3
pywebview==6.2.1
```

Development instructions target Python 3.12. The requirements file is not a complete lock of all transitive/build dependencies. Reproduce and test the environment before upgrading packages.

`app.py` starts a threaded Werkzeug server bound to `127.0.0.1`, with a random per-launch token and OS-selected port. `X-Moto-Token` is used for API authentication; resource URLs can carry the token. It opens a native pywebview window (1500x960, minimum 1100x760). There is one active `Document` global, protected by `LOCK`; this is not a multi-document/multi-user service.

Command-line options: `--port`, `--no-browser`, `--open`, `--session-file`, `--state-file`. Session file records URL/token/port for local tests; don't publish a live token. `--no-browser` serves without desktop window.

On window close: shut down server, clean temporary directory, then packaged build calls `os._exit(0)` to avoid lingering WebView2 helper threads. Shutdown had previously frozen; preserve this behaviour unless replacing it with a tested alternative. Save project before closing; do not assume crash recovery or autosave.

`Document` holds PSD, layer IDs, assets, render caches and state. Important state fields:
`name, artworks, visibility, shading, placement, normal, normal_layers, spec, palette`.

Artwork fields include `id, asset, name, x, y, width, height, rotation, opacity, visible`, optional `color` and `text`. Editable text includes `value, font, size, stroke, fill, outline, base_width, base_height, gradient`.

`render_text_bitmap` builds the same output used for preview and final text, including glyph-mask gradients and outlines. `art_image` can rerender text at required resolution. Final diffuse composition temporarily inserts a PSD PixelLayer at the selected anchor and removes it in a finally block after compositing. Preserve PSD blend modes/masks/group behaviour and exception cleanup.

Important backend areas/functions: `Document`, `render_text_bitmap`, `clipboard`, `remove_white_background`, `sample_colour`, `save_logo`, `delete_logo`, `save_layout`, `add_layout`, `delete_layout`, `viewer_map`, `render_live`, `project_bytes`, `load_project`, `install_game_pnt`, `export`, `main`. Inspect current decorators for route signatures rather than guessing request schemas.

Useful endpoints include `/api/text/preview`, `/api/sample-colour`, `/api/render/live`, `/api/viewer/map/<kind>`, `/api/layouts`, `/api/layouts/<key>/add`, DELETE `/api/layouts/<key>`, DELETE `/api/logos/<key>` and `/api/project/open`.

### PNT binary details

Own independent implementation in `packing.py`, not code integrated from PaintHub/PaintEd:

- Header `PNT\0`, 100-byte null-padded CP1252 paint name, little-endian texture count.
- Each entry: 100-byte texture stem, width/height, MD5 of complete source TGA bytes, compressed payload size, payload.
- Payload: eight zero reserved bytes followed by raw DEFLATE of bottom-up RGBA pixels.
- Stems are `rider`, `rider_n`, `rider_r` (without extension in the container).
- Name validation: nonempty, at most 99 encoded bytes, no nulls; unsupported CP1252 characters are rejected.
- `read_pnt` validates/decompresses for tests, including dimensions, output length, stream end and trailing bytes.

### Saved data

Under the Windows account's `%LOCALAPPDATA%/Moto Gear/`:

- `Projects/`: local editable project library.
- `Logos/`: saved logo PNG plus JSON metadata.
- `Layouts/`: UUID-named ZIPs with `layout.json` and `assets/<id>.png`; no source PSD inside a layout.

Portable `.motogear` is a ZIP containing source PSD, state JSON and artwork images. Palette is in project state and frontend localStorage. Layout save uses temporary file then atomic replacement. Layout IDs are validated as 32 lowercase hex characters; apply stages images and generates fresh IDs. Current layout import checks images up to 64 megapixels and scaled dimensions 1–16384.

Never clear these directories to solve an update problem. Use isolated test LOCALAPPDATA.

## Performance work already done

- requestAnimationFrame coalesces UI redraws; approximately 350ms proof-render debounce.
- Avoid fetching full composite on every drag movement.
- Request epochs stop stale render responses from replacing newer state.
- Direct PNG live-render responses and retry handling.
- PNG compression level 2 for responsive previews.
- Bounded decoded NumPy pixel cache: 192MB total; arrays over 64MB skipped, defensive copies prevent cache mutation.
- Affected-region compositing for compatible PSDs with unchanged static base. Unsupported effects/clipping/complex dependencies fall back to full composite.
- Norm/Spec lazy previews; viewer map cache.
- A real 4096px Fox PSD rotated-logo update was measured at 1.13s versus 8.38s full composition with identical pixels in the v1.1 test. This is one benchmark, not a universal promise.
- Some complex 4K PSDs still take around a minute to prepare/export. Do not replace accurate shading with a cheap faded overlay to make timing look faster.

## Building and distributing

Existing local runtimes (check availability before using on a different machine):

```text
Python: C:\Users\frase\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe
Node: C:\Users\frase\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe
```

The local development dependency directory is `work/deps` (set PYTHONPATH when using existing environment). Spec has absolute owner-machine paths; make them portable before building elsewhere.

Typical sequence from workspace root, using the appropriate Python executable:

```powershell
$env:PYTHONPATH = 'work/deps'
python -m PyInstaller --noconfirm --distpath work/revised-dist --workpath work/revised-build 'work/Moto Gear.spec'
python work/release/build_payload.py
python -m PyInstaller --noconfirm --onefile --windowed --name 'Moto Gear v1.3 Setup' --icon outputs/Moto-Gear/source/icon.ico --add-data 'work/release/payload.zip;.' --distpath outputs/Moto-Gear/release --workpath work/release/installer-build-v1.3 --specpath work/release work/release/installer.py
```

Use absolute paths for icon/payload/script if PyInstaller resolves relative paths against the spec location. Update names/version paths for a new release. Build specification collects static assets, fonts, icon, psd_tools/skimage/scipy, aggdraw and edgechromium, excludes Qt bindings, and creates a windowed application directory.

Payload builder includes README/VERSION/CHANGELOG/notices, excludes dependency tests/cache files, and asserts no PSD, `.motogear`, TGA or PNT is bundled. Do not ship personal templates, libraries or projects.

Installer uses ctypes Windows dialogs, not Tkinter. An early installer failed on friends' machines with missing tkinter; do not reintroduce that dependency. Default per-user install location is `%LOCALAPPDATA%/Programs/Moto Gear`; creates Desktop and Start menu shortcuts. Uses staged install/backup replacement. Test switches: `--quiet --no-shortcuts --target <test-folder>`.

Runtime requirements: Windows and WebView2. Python/Photoshop/Blender are not required for friends. Installer is unsigned. It is one file to send, but installs the app with resources; do not distribute just the inner app EXE.

Release procedure: update version label and VERSION/changelog/docs, test source, build app, build payload/installer, clean-install into isolated folder, launch installed copy and test essential flows, compare installed assets to build, create source snapshot, then copy verified installer to Desktop. Preserve older releases and avoid overwriting a running EXE. Check shortcut target exists; earlier shortcuts broke by pointing at nonexistent old output paths.

Restricted Codex environment note: temp-directory permissions caused failures in October. Set TEMP and TMP to an existing writable workspace test directory if needed. Localhost tests required network permission and a newly started server after permission was granted. These are development sandbox issues, not automatic evidence the installed product is broken.

## Test history and honest status

Current v1.3 passed:

- `work/test_v13_backend.py`: layout save/list/apply/delete, independent assets/IDs, 128-to-256 coordinate scaling, colour/rotation/opacity preservation, target placement preservation, editable gradient text transfer and project roundtrip.
- `work/test_v13_packaged.py`: actual packaged app startup and HTTP flow, synthetic PSD upload, bundled font lookup, gradient text creation, persisted layouts save/apply/delete.
- JavaScript syntax check.
- Clean single-file installer extraction; installed EXE/HTML/JS hashes matched build and VERSION was 1.3.

**v1.3 visual browser verification did not complete.** `work/test_v13.cjs` exists but is not a passing test result. Edge failed to launch in the restricted environment and an in-app browser attempt timed out. Do not report this as tested. 3D/PNT were not fully rerun for v1.3; their prior history is below.

Earlier tests, with release-specific evidence (inspect before rerunning):

- `test_v12_backend.py`, `test_v12.cjs`, `test_v12_real3d.cjs`: saved-logo deletion/cancel/independent project copy; Normal/Reflection toggles changed actual rendered pixels, black background, no GL/JS errors, real 4K preview.
- `test_v111_psd.py`, `test_v111.cjs`: panning and previously failing combined shading/Normal PSD; synthetic 70-layer Normal group; black-alpha exports.
- `test_v11_backend.py`, `test_v11_performance.py`, `v11-performance.json`: gradients/library and exact-pixel affected-region rendering comparison.
- `test_studio_ui.cjs`: artwork visibility with delayed/failing shading, retry, name/number creation, PNT flow, smaller viewport. Waits for setup response to avoid stale prior-document state.
- `test_release_pnt.py`: real 4K exports, bit depths, black alpha, PNT MD5/pixel checks.
- `test_fox_shading.py`: real 4K under-shading versus above-shading comparison.
- `test_save_resume.py`: editable project roundtrip and export, invalid-path handling.
- `test_font_preview.cjs`: live font preview.

For the next release, prioritise visible UI testing of v1.3 layouts and gradient swatches, then relevant regressions. Test one realistic PSD, save/reopen, under-shading rendering, text scaling and all exported alpha bytes. In-game verification remains a distinct step from binary tests even though the owner has confirmed the existing packer works.

## Model and PSD fixtures

Original model supplied:
`C:\Users\frase\Downloads\WBD Rider Model.blend`

It was no longer present at that path when checked in October. Current converted mesh is available in `source/static/rider.json`; normal app builds do not need Blender or the .blend. Export used the original paint UV rider jersey/pants mesh, 30,324 triangle vertices. Blender was installed at `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`.

`work/export_rider.py` is the conversion script. `work/add_rider_tangents.py` converted stride-8 mesh data to stride-12 tangents with area weighting and mirrored-UV handedness; do not rerun it blindly on current stride-12 data.

Useful real PSD fixtures on owner's N: drive (may not be accessible elsewhere):

- `N:/RIDER GEAR PSD's/Rider Gear/FOX/2027/2027-Fox-360-Temper-By-Cquatty-and-KD/2027 Fox 360 Temper By Cquatty and KD.psd`
- `N:/RIDER GEAR PSD's/Rider Gear/FOX/2026 FOX FLEXAIR DNGR ST LOUIS BY RC.psd`
- Original example: `N:/RIDER GEAR PSD's/Rider Gear/Stryder Gear/2019 Shift Black Label - Light/2019 Shift Black Label - Light.psd`

For the failing Fox fixture: outer group `4 SHADING/NORM`, dedicated `4.2 NORM`, child `4.2.0 Layer 46`. `4.1 Layer 861 copy 2` is outside the dedicated Normal group and must not be included as Normal merely due to the parent's name.

## Known limitations / work not implemented

- Protected online DGS product library was discussed but is not implemented.
- Batch packing/export was discussed as a reference capability but is not implemented in the current release.
- No exact Photoshop renderer: psd-tools may differ on complex effects, adjustment layers, fonts and smart objects. Do not promise arbitrary PSD compatibility.
- No direct native editing of existing PSD text or embedded smart-object contents.
- No retained SVG vector editor; imported SVGs are rasterised.
- No exact MX Bikes engine shader in preview; original rider UV layouts required.
- Layout transfer does not remap artwork intelligently across different UV arrangements.
- Saved logo/layout libraries are local to a Windows account, not automatically synchronised to friends.
- Not an automatic updater or cloud service; friends receive a new installer for releases.
- No guarantee of zero issues on every PC; ensure clean installation and visual tests before distribution.

## Suggested first action for Claude

Read README, CHANGELOG, TESTED, source and build scripts. Confirm you have the actual source/assets and ask the owner for the next desired change rather than inventing a redesign. If tasked with stabilising the current release, close the documented v1.3 visual-testing gap first. Preserve the existing working export contract and user libraries throughout.
