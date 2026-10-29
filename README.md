# Dirt Gear v1.0

A local Windows editor for MX Bikes rider gear. Open a creator's gear PSD, choose colourways, add your logos, name and number beneath the shading, check it on the 3D rider, and pack a game-ready paint. No Photoshop, PaintHub or PaintEd needed. Dirt Gear is the successor to Moto Gear v1.3.

## Install

Run **Dirt Gear v1.0 Setup.exe** and choose **Yes**. It installs for your Windows account (no admin needed) and adds Desktop and Start menu shortcuts. Microsoft Edge WebView2 Runtime is required (already on Windows 10/11 in most cases).

If you used Moto Gear, your saved projects, logos and layouts are copied into Dirt Gear the first time it opens. Moto Gear's own folder isn't changed, so both apps can live side by side.

## Using it

1. **Open PSD** (top bar or the start screen). Dirt Gear finds the Norm and Spec maps itself. If there's no Spec, it makes a black one.
2. **Layers** (left): click the eye to show or hide a layer. Lock icons mark Norm/Spec map layers, which are used automatically for export. Tags show SHADE, NORM, SPEC and ART (smart objects).
3. **Add to your gear** (right): add a logo or image (PNG, JPG, SVG), paste with Ctrl+V, drag files onto the canvas, or add a **Name** or **Number** in any bundled BYD/MX font, with an outline and a gradient if you want them.
4. **Place it**: drag to move, drag a corner to resize (hold Shift to stretch), and use the round handle to rotate (snaps to 15°, Shift for free rotation). Alt-drag pans, the scroll wheel zooms, arrow keys nudge, Ctrl+Z / Ctrl+Shift+Z undo and redo, and Delete removes.
5. **Under the shading**: drag the green **Your added layers** strip onto a PSD layer to put all your artwork below it. Reorder your own layers by dragging them or using the arrows.
6. **Check it**: Diffuse / Norm / Spec tabs, **3D preview** on the rider, and **Check final rendering** for the exact export image.
7. **Finish & ride** (bottom right): name the gear, pick the rider model and click **Pack & install in MX Bikes**. Restart MX Bikes to see it. **Export .pnt** (top bar) or **3 TGAs (.zip)** let you save the files anywhere.
8. **Save for later** keeps an editable project in your library, and **Continue** is offered on the start screen. **Portable project** saves a `.dirtgear` file you can move to another PC (old `.motogear` files still open).

Saved logos, logo layouts and HEX colour swatches work as they did in Moto Gear v1.3.

## Export contract (unchanged from Moto Gear)

| File | Format | Alpha |
| --- | --- | --- |
| `rider.tga` | 24-bit RGB | none |
| `rider_n.tga` | 32-bit RGBA | every byte 0 |
| `rider_r.tga` | 32-bit RGBA | every byte 0 |

`.pnt` files use Dirt Gear's own independent writer (`source/packing.py`).

## Limits

8-bit RGB PSDs up to 8192 × 8192. PSD rendering uses psd-tools, not Photoshop, so complex effects can differ, so check the final rendering. Existing PSD text and smart objects can't be edited as text or vectors. The 3D preview uses studio lighting, not the MX Bikes shader.

## Building (developers)

Releases are built automatically: changing `VERSION.txt` on main (or running the workflow from the Actions tab) runs `.github/workflows/release.yml` on a GitHub Windows machine. It builds the app and installer, clean-installs it, runs the backend tests against the installed copy, and then publishes `Dirt Gear vX Setup.exe` on the Releases page.

To build locally instead:

Requires Windows and Python 3.12. From this folder:

```powershell
powershell -ExecutionPolicy Bypass -File build\build.ps1
```

This creates a `.venv`, builds `dist\Dirt Gear\`, then `release\Dirt Gear v1.0 Setup.exe`. To run from source instead: `pip install -r source\requirements.txt` then `python source\app.py`.

Tests: `tests/test_backend.py` (exports, black alpha, PNT, projects, library migration) and `tests/test_ui.cjs` (Playwright walkthrough). Start the app with `python source/app.py --no-browser --session-file <dir>/session.json`, create `<dir>/fixtures/test-gear.psd` with `tests/make_test_psd.py`, then pass `<dir>` to either test. The old Moto Gear suites are kept in `tests/legacy-moto-gear/` for reference.

See `CLAUDE-HANDOVER.md` for the full technical handover.
