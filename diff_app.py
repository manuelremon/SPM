from pathlib import Path
import difflib
orig = Path('src/frontend/app.js').read_text(encoding='utf-8', errors='replace').splitlines()
new = Path('src/frontend/app.js.codexbackup').read_text(encoding='utf-8', errors='replace').splitlines()
for line in difflib.unified_diff(orig, new, fromfile='app.js', tofile='app.js.codexbackup', n=3):
    print(line)
