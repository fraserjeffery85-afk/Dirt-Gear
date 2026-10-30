"""Write notes.md from the newest '## v...' section of CHANGELOG.md."""
import re
from pathlib import Path

text = Path('CHANGELOG.md').read_text(encoding='utf-8')
section = re.split(r'(?m)^## ', text)[1]
body = section.split('\n', 1)[1].split('\n---\n')[0].strip()
Path('notes.md').write_text(body + '\n', encoding='utf-8')
print(body)
