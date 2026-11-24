"""Converte o Markdown dos cards [CONS] (ReproSteps) em HTML para a descrição do GLPI."""
import html, re

def inline(t):
    t = html.unescape(t)
    t = html.escape(t, quote=False)
    t = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'<a href="\2"><img src="\2" alt="\1" style="max-width:900px"></a>', t)
    t = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', t)
    t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
    return t

def md2html(md):
    out, lines, i = [], md.replace('\r', '').split('\n'), 0
    while i < len(lines):
        l = lines[i]
        if l.strip().startswith('|') and i + 1 < len(lines) and re.match(r'^\s*\|[\s:|-]+\|\s*$', lines[i + 1]):
            cells = lambda s: [c.strip().replace('\\|', '|') for c in re.split(r'(?<!\\)\|', s.strip().strip('|'))]
            rows = ['<tr>' + ''.join(f'<th>{inline(c)}</th>' for c in cells(l)) + '</tr>']
            i += 2
            while i < len(lines) and lines[i].strip().startswith('|'):
                rows.append('<tr>' + ''.join(f'<td>{inline(c)}</td>' for c in cells(lines[i])) + '</tr>')
                i += 1
            out.append('<table border="1" cellpadding="4" style="border-collapse:collapse">' + ''.join(rows) + '</table>')
            continue
        m = re.match(r'^(#{1,6})\s+(.*)', l)
        if m:
            n = min(len(m.group(1)) + 2, 6)
            out.append(f'<h{n}>{inline(m.group(2))}</h{n}>')
        elif re.match(r'^\s*[-*]\s+', l):
            items = []
            while i < len(lines) and re.match(r'^\s*[-*]\s+', lines[i]):
                items.append('<li>' + inline(re.sub(r'^\s*[-*]\s+', '', lines[i])) + '</li>')
                i += 1
            out.append('<ul>' + ''.join(items) + '</ul>')
            continue
        elif re.match(r'^\s*\d+\.\s+', l):
            items = []
            while i < len(lines) and re.match(r'^\s*\d+\.\s+', lines[i]):
                items.append('<li>' + inline(re.sub(r'^\s*\d+\.\s+', '', lines[i])) + '</li>')
                i += 1
            out.append('<ol>' + ''.join(items) + '</ol>')
            continue
        elif l.strip():
            para = [inline(l)]
            while i + 1 < len(lines) and lines[i + 1].strip() and not re.match(r'^\s*([-*|#]|\d+\.)', lines[i + 1]):
                i += 1
                para.append(inline(lines[i]))
            out.append('<p>' + '<br>'.join(para) + '</p>')
        i += 1
    return '\n'.join(out)
