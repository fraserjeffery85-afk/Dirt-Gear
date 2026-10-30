# Updates: one-time setup and releasing

Dirt Gear checks GitHub Releases each time it starts, the same way Optic and Moto Lines Studio do. When there's a newer version it shows a bar at the top. **Download and install** fetches the installer, checks its signature and SHA-256, closes Dirt Gear, updates it in place and reopens it. Projects, logos, layouts and settings in `%LOCALAPPDATA%\Dirt Gear` are never touched.

## One-time setup (about 2 minutes)

1. **Add the signing key secret.** In the repository open *Settings → Secrets and variables → Actions → New repository secret*. Name it `UPDATE_SIGNING_KEY` and paste the whole contents of `dirt-gear-update-signing-key.pem`, including the `BEGIN` and `END` lines.
   - Keep a backup of that file somewhere safe and offline (a USB stick or password manager). Don't share it and never commit it (`.gitignore` blocks `*.pem`, except the public key in `source/`).
   - If it leaks, someone could sign fake updates. If it's lost, run `python tools/keygen.py` to make a new pair and commit the new `source/update_public_key.pem`. Everyone then installs that release once by hand.
2. **Keep the repository public** so the people you share Dirt Gear with can check for updates without logging in. A private repo makes the check fail quietly.
3. **Install once from a release** (v1.0.2 or later). Copies built anywhere else, and versions before 1.0.2, don't check for updates.

Until the secret is added, releases still publish and the app still announces them, but the button says **Open download page** instead of installing.

## Releasing an update

1. Change the code, raise the number in `VERSION.txt` (e.g. 1.0.2 → 1.0.3) and add a `## v1.0.3` section at the top of `CHANGELOG.md`. That section becomes the release notes and the app's *What's new* text.
2. Push to `main`. The *Build & release* action builds, tests and signs the release, then publishes `Dirt-Gear-Setup-<version>.exe`, `update.json` and `update.json.sig`. GitHub creates the `v1.0.3` tag itself. Pushes that don't change `VERSION.txt` don't build a release. Running the workflow again for the same version publishes nothing.
3. With the key set, the action also runs an **end-to-end self-update test** on Windows before publishing. An installed copy updates itself from a local copy of the new release, and the release is only published if that works.
4. The next time anyone opens Dirt Gear, they see "Dirt Gear 1.0.3 is available".

You can also start the action by hand: *Actions → Build & release → Run workflow*. Or ask Claude to "release it".

## What happens on each computer

- About 4 seconds after Dirt Gear starts, it asks GitHub for the latest release (a few kilobytes). The installer (about 100 MB) downloads only when someone clicks **Download and install**.
- `update.json` must carry a valid Ed25519 signature from your key, and the download must match its size and SHA-256. Anything else is refused.
- **Skip this version** hides that version until a newer one appears. Clicking the version label (top left) opens *About & updates*: **Check for updates** still finds a skipped version, and the start-up check can be turned off there.
- Downloads go to `%LOCALAPPDATA%\Dirt Gear\updates` and are deleted the next time Dirt Gear starts.
- The installer runs in update mode (`--update`). It waits for Dirt Gear to close, swaps the program folder with a backup (rolling back if anything fails) and reopens Dirt Gear.
- If you have unsaved changes, Dirt Gear asks before restarting.

## Discord announcements

When a release is published, the release workflow posts it to Discord with the full release notes, the Dirt Gear logo and a download link.

1. In Discord: *Server Settings → Integrations → Webhooks → New Webhook*, pick the channel, then *Copy Webhook URL*.
2. In GitHub: *Settings → Secrets and variables → Actions → New repository secret*. Name it `DISCORD_WEBHOOK` and paste the URL. A URL ending in `/github` works too.
3. If you also added a GitHub repository webhook (*Settings → Webhooks*) pointing at Discord, delete it, or every release posts twice.

To post the latest release again, go to *Actions → Announce latest release on Discord → Run workflow*. Without the secret, releases still publish and the post is skipped.
