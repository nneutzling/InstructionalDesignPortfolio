"""Copy one section of the Larch & Lichen sockeye lesson into a standalone portfolio page.
Usage: python3 tools-extract-larch.py <larch site dir> <section marker> <out dir> <title> <description>"""
import sys, re
site, marker, out, title, desc = sys.argv[1:6]
src = open(f'{site}/lesson-sockeye-salmon.html', encoding='utf-8').read()
head = src[:src.index('<nav class="topbar"')]
head = re.sub(r'<title>.*?</title>', f'<title>{title}</title>', head, count=1)
head = re.sub(r'<meta name="description" content="[^"]*">', f'<meta name="description" content="{desc}">', head, count=1)
def section(name):
    start = src.index(f'<!-- ===================== {name} ===================== -->')
    nxt = src.index('<!-- =====================', start + 10)
    return src[start:nxt]
controls = section('NARRATION CONTROLS')
body = section(marker)
scripts = src[src.index('<script src="dc-runtime.js"></script>'):]
page = (head +
 '<main class="lesson salmon-lesson" style="--accent:#C5852A;--accent-deep:#8a5a14;--accent-rgb:197,133,42;">\n'
 '  <header class="ls-head wrap">\n'
 '    <span class="wordmark" style="font-family: var(--serif); font-size: 20px; color: #2E4034;">Larch &amp; Lichen Learning</span>\n'
 '    <span style="font-size: 13px; color: #6A5743;">From the <em>Autumn Return</em> lesson · grades 3 to 5</span>\n'
 '  </header>\n  <div id="dc-root">\n'
 '<div style="width: 100%; min-height: 100vh; box-sizing: border-box; display: flex; flex-direction: column; align-items: center; background: #F5F0E6; padding-bottom: 48px;">\n'
 + controls + body + '</div>\n</div>\n</main>\n' + scripts)
open(f'{out}/index.html', 'w', encoding='utf-8').write(page)
print('wrote', out)
