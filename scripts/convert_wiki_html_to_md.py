import os
import re
from html import unescape

SRC = os.path.join(os.path.dirname(__file__), '..', 'docs', 'wiki', 'pages')
OUT = os.path.join(os.path.dirname(__file__), '..', 'docs', 'wiki', 'export')

os.makedirs(OUT, exist_ok=True)

TAG_RE = re.compile(r'<[^>]+>')

def html_to_md(html: str) -> str:
    # Normalize newlines
    s = html
    # handle codeblocks: <div class="codeblock">...</div>
    def repl_codeblock(m):
        inner = m.group(1)
        inner = inner.replace('<br>', '\n').replace('<br/>','\n').replace('<br />','\n')
        inner = TAG_RE.sub('', inner)
        return '\n```\n' + inner.strip() + '\n```\n'
    s = re.sub(r'<div[^>]+class="codeblock"[^>]*>(.*?)</div>', repl_codeblock, s, flags=re.S)

    # headings
    for i in range(6,0,-1):
        s = re.sub(fr'<h{i}[^>]*>(.*?)</h{i}>', lambda m: '\n' + ('#'*i) + ' ' + TAG_RE.sub('', m.group(1)).strip() + '\n', s, flags=re.S)

    # paragraphs to double newline
    s = re.sub(r'<p[^>]*>(.*?)</p>', lambda m: '\n' + TAG_RE.sub('', m.group(1)).strip() + '\n', s, flags=re.S)

    # list items
    s = re.sub(r'<ul[^>]*>(.*?)</ul>', lambda m: '\n' + re.sub(r'<li[^>]*>(.*?)</li>', lambda it: '- ' + TAG_RE.sub('', it.group(1)).strip() + '\n', m.group(1), flags=re.S) + '\n', s, flags=re.S)

    # inline code
    s = re.sub(r'<code[^>]*>(.*?)</code>', lambda m: '`' + TAG_RE.sub('', m.group(1)).strip() + '`', s, flags=re.S)

    # links
    s = re.sub(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', lambda m: '[' + TAG_RE.sub('', m.group(2)).strip() + '](' + m.group(1) + ')', s, flags=re.S)

    # br to newline
    s = s.replace('<br>', '\n').replace('<br/>','\n').replace('<br />','\n')

    # remove any remaining tags
    s = TAG_RE.sub('', s)

    # unescape HTML entities
    s = unescape(s)

    # collapse multiple blanklines to two
    s = re.sub(r'\n\s*\n\s*\n+', '\n\n', s)

    return s.strip() + '\n'


def convert_all():
    files = [f for f in os.listdir(SRC) if f.endswith('.html')]
    if not files:
        print('No html files found in', SRC)
        return
    for fn in files:
        p = os.path.join(SRC, fn)
        with open(p, 'r', encoding='utf-8') as f:
            html = f.read()
        md = html_to_md(html)
        outname = os.path.splitext(fn)[0] + '.md'
        outpath = os.path.join(OUT, outname)
        with open(outpath, 'w', encoding='utf-8') as o:
            o.write(md)
        print('Converted', fn, '->', outpath)

if __name__ == '__main__':
    convert_all()
