# Moto Gear v1.3

A local Windows editor for MX Bikes rider gear. No PaintHub or PaintEd is required.

Logos and text stay visible while moving, resizing, or waiting for PSD shading. The footer distinguishes the editing preview from the final shaded result; Retry shading is available after a failed refresh. New text chooses a contrasting starting colour.

## Start

For another Windows PC, run **Moto Gear v1.3 Setup.exe** from the `release` folder and choose **Yes** when the setup prompt appears. It installs Moto Gear for that Windows account and creates desktop and Start menu shortcuts. The installer includes the BYD and MX fonts from this build, but not your PSDs or saved projects. Microsoft Edge WebView2 Runtime is required to display the app.

To make a paint appear in MX Bikes, choose the rider model under **Save your gear** and click **Pack & install in MX Bikes**. Moto Gear reads the game's configured mods folder from `PiBoSo/MX Bikes/global.ini` and places the paint in that model's `paints` folder. Restart MX Bikes to refresh its paint list. **Export .pnt** still lets you save a portable file wherever you choose; that file will not appear in game until it is placed in the correct model's paint folder.

To run a portable build, open **Moto Gear.exe** and keep its `_internal` folder beside it. Moto Gear opens in its own native desktop window. All processing stays on the computer; no account or internet connection is required for editing.

1. Choose **Open PSD**, or **Open project file** to continue a portable `.motogear` file. After using **Save for later**, the start screen also offers **Continue last project**.
2. Moto Gear finds Norm and Spec groups or layers automatically. Multiple layers within a Norm group combine into one exported Norm texture. If the PSD has no Spec group or layer, Moto Gear creates a solid black Spec texture automatically.
   Every PSD layer appears in the left panel with a small preview and groups expanded initially. Toggle existing designs off there. Each smart object remains one layer; its embedded contents are not split out. Norm and Spec map layers remain protected because they are used automatically for export.
3. Add PNG/JPG/SVG artwork, drag a file onto the canvas, or paste an image with Ctrl+V. Paste checks the Windows clipboard for SVG first, then alpha-preserving PNG, then a bitmap from Illustrator. Illustrator's native-only clipboard formats are not supported; SVG/PNG import is the fallback. SVG artwork is rasterized when imported. If only a flattened white bitmap is available, select it and use **Remove white background**; edge-connected white becomes transparent.
4. Your added logos, names and numbers appear as a group among the PSD layers. Drag the **Your added layers** heading onto any PSD layer to put the whole section below it, such as a shading layer. Drag the individual artwork rows or use their arrow buttons to change their order within the section. Drag artwork on the canvas to place it. Drag a corner or edge handle to resize proportionally; hold Shift while dragging to stretch or narrow it freely. Names and numbers have a separate **Text width** control to narrow or widen letters independently of height. Text is rerendered from the installed font at the required output size so enlarging it does not upscale a small text bitmap. SVGs are rasterized at the PSD's resolution. The round handle rotates artwork, with optional 15° snapping (hold Shift for free rotation). Exact placement, dimensions, rotation and opacity are available on the right. Scroll to zoom; Alt+drag to pan. Ctrl+Z undoes artwork edits; Ctrl+Shift+Z redoes them. Arrow keys nudge (Shift for larger steps).
   Use **Add name** or **Add number** for text. Choose a font, colour, size and outline. The bundled BYD and MX fonts are available inside Moto Gear without installing them in Windows. Select a text layer and choose **Edit text & font** to change it later. The app also reads other fonts installed on the PC.
5. Save exact HEX colour codes as reusable swatches. A swatch can colour new text or apply an optional single-colour tint to selected artwork. Saved swatches stay in the editable project and on this PC. The canvas starts from the PSD's accurately composited appearance. While moving or changing artwork, it shows the artwork at its chosen opacity immediately; after you release it, the accurate shaded preview updates. Zooming in loads a higher-resolution preview, up to 4096 pixels. Use **Check final rendering** before exporting a new template. Norm and Spec previews load when first opened to reduce initial preparation time.
6. Enter a gear name, then choose **Export .pnt** or **Export 3 TGAs (.zip)**. A Windows Save As dialog lets you choose the destination folder.
7. **Save for later** keeps an editable project in this PC's Moto Gear library so you can return to it next time. **Save portable project file** creates a `.motogear` file you can move to another PC. Both include the source PSD, artwork, text and layer setup, and leave the original PSD untouched.

## Fixed exports

- `rider.tga`: 24-bit RGB; no alpha.
- `rider_n.tga`: 32-bit RGBA; every alpha byte is zero.
- `rider_r.tga`: 32-bit RGBA; every alpha byte is zero.
- A generated Spec has pitch-black RGB as well as pitch-black alpha.
- RGB texture data is retained when alpha is cleared.
- `.pnt` uses Moto Gear's own writer, checked against the supplied existing paint container and its original TGAs.

## Scope and limits

V1 accepts 8-bit RGB PSDs up to 8192 × 8192. Complex 4096px PSDs can take around a minute to prepare or export. PSD rendering uses psd-tools rather than Photoshop, so complex effects, adjustments, smart objects and fonts can differ; inspect the final rendering. Existing text/smart-object layers are not directly editable as text or vectors. Use layer visibility to hide prior logos or names.

This build targets rider textures using the `rider`, `rider_n`, and `rider_r` names. It does not include the protected online DGS library or batch export yet. The packer has structural and pixel round-trip checks; an actual MX Bikes in-game check is still required before distributing paints.

The included **Shift Black Label - Clean.motogear** hides the LOGOS, ARMS, ARMS copy and Name Number groups in the supplied PSD. The original PSD remains untouched.

## Development

Source is included in `source/`. Install `source/requirements.txt` in Python 3.12 and run `python app.py` from that directory. The local service binds only to 127.0.0.1 and uses a random per-launch token. Closing the app also stops its local service. Save your editable project before closing the desktop window.

Third-party libraries retain their respective licenses. See `THIRD_PARTY_NOTICES.txt` and the bundled package metadata. Moto Gear's PNT code is an independent implementation based on inspection of the user-supplied files; it does not incorporate PaintHub code.


## New in v1.1

Open **3D preview** to inspect the current design on the included WBD rider mesh. Drag to rotate and scroll to zoom. The preview uses diffuse, Normal and Reflection map RGB under studio lighting. It approximates the materials rather than reproducing the game's shader exactly. Templates must match the original rider UV layout.

Enable **Gradient fill** when adding or editing a name or number. Pick each colour from the gear, then choose the direction. Colours are sampled from the full-resolution template. Press Escape to cancel sampling.

Select an added logo and choose **Save to logo library**. In another project, choose **Saved logos** to reuse it. This library stays on the current Windows account; portable projects still contain their own artwork.

In 3D preview, Shift-drag or right-drag to pan while zoomed in, or select Pan and drag normally. Up/down buttons also move the model. Reset view restores the centre and zoom.

## New in v1.2

Saved logos now have a **Delete** button. Confirm to remove only that library entry; artwork already added to projects stays intact.

The 3D backdrop is black. **Normal detail** and **Reflections** switches let you compare each map. The Normal map changes surface lighting; Reflection RGB controls studio reflections. Export alpha channels remain pitch black.

## New in v1.3

Use **Logo layouts → Save current layout** to save your added logos, names and numbers as a set. Open another PSD, then choose **Logo layouts → Apply**. Positions and sizes scale with texture dimensions, but check placement when templates use different UVs. Layers stay editable and one Undo removes the applied set. Template/baked-in artwork is not transferred.

Choose saved swatches underneath each gradient colour to set the start and end independently.

Send **Moto Gear v1.3 Setup.exe** directly to friends. No ZIP or separate resource folder is required.
