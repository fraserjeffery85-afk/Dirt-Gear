"""Post a release announcement (with the release notes) to a Discord channel.

Usage: python tools/discord_notify.py <version> <notes.md> <release url>
Reads the webhook from the DISCORD_WEBHOOK environment variable (repository
secret). Does nothing if it isn't set, so releases never fail because of it."""
import json
import os
import sys
import urllib.request
from pathlib import Path

version, notes_path, url = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
hook = os.environ.get('DISCORD_WEBHOOK', '').strip()
if not hook:
    print('DISCORD_WEBHOOK not set - skipping Discord announcement.')
    sys.exit(0)
if hook.endswith('/github'):          # the GitHub-format address won't take custom posts
    hook = hook[: -len('/github')]
repo = os.environ.get('GITHUB_REPOSITORY', 'fraserjeffery85-afk/Dirt-Gear')
setup = f'https://github.com/{repo}/releases/download/v{version}/Dirt-Gear-Setup-{version}.exe'
logo = f'https://raw.githubusercontent.com/{repo}/main/docs/dirt-gear-logo.png'

notes = notes_path.read_text(encoding='utf-8').strip()
footer_links = f'\n\n**[Download Dirt-Gear-Setup-{version}.exe]({setup})** · [Release page]({url})'
limit = 4096 - len(footer_links) - 40
if len(notes) > limit:                # Discord embed descriptions max out at 4096 characters
    notes = notes[:limit].rsplit('\n', 1)[0] + f'\n… [full notes]({url})'

payload = {
    'username': 'Dirt Gear',
    'avatar_url': logo,
    'embeds': [{
        'title': f'Dirt Gear {version} is out',
        'url': url,
        'color': 0xD7FF3C,
        'thumbnail': {'url': logo},
        'description': notes + footer_links,
        'footer': {'text': 'Already on 1.0.2 or later? Open Dirt Gear and click Download and install.'},
    }],
    'allowed_mentions': {'parse': []},
}
request = urllib.request.Request(hook + ('&' if '?' in hook else '?') + 'wait=true',
                                 data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json', 'User-Agent': 'Dirt-Gear-Release'})
with urllib.request.urlopen(request, timeout=20) as response:
    print('Posted to Discord:', response.status)
