# -*- coding: utf-8 -*-
"""零依赖 md -> 带样式 HTML 转换器（供 Edge headless 打印 PDF）"""
import re, html, sys, io

def inline(t):
    t = html.escape(t)
    # 行内代码
    t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
    # 粗体
    t = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', t)
    return t

def render_table(rows):
    cells = []
    for r in rows:
        s = r.strip()
        if not s:
            continue
        if re.match(r'^\|?[\s\-:|]+\|?$', s):  # 分隔行
            continue
        cells.append([c.strip() for c in s.strip('|').split('|')])
    if not cells:
        return ''
    head = cells[0]
    body = cells[1:]
    thead = '<tr>' + ''.join(f'<th>{inline(c)}</th>' for c in head) + '</tr>'
    tbody = ''.join('<tr>' + ''.join(f'<td>{inline(c)}</td>' for c in r) + '</tr>' for r in body)
    return f'<table><thead>{thead}</thead><tbody>{tbody}</tbody></table>'

def md_to_html(text):
    lines = text.split('\n')
    out = []
    i, n = 0, len(lines)
    in_code = False
    code_buf = []
    table_buf = []
    list_stack = []  # ('ul'|'ol', count)

    def close_list():
        nonlocal list_stack
        while list_stack:
            tag = list_stack.pop()[0]
            out.append(f'</{tag}>')

    def open_list(tag):
        if list_stack and list_stack[-1][0] == tag:
            list_stack[-1][1] += 1
        else:
            close_list()
            list_stack.append([tag, 1])
            out.append(f'<{tag}>')

    while i < n:
        line = lines[i]
        stripped = line.strip()
        # 代码块
        if stripped.startswith('```'):
            if in_code:
                out.append('<pre><code>' + html.escape('\n'.join(code_buf)) + '</code></pre>')
                code_buf = []
                in_code = False
            else:
                in_code = True
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue
        # 表格
        if stripped.startswith('|') and '|' in stripped:
            table_buf.append(line)
            i += 1
            continue
        if table_buf:
            close_list()
            out.append(render_table(table_buf))
            table_buf = []
            continue
        # 标题
        m = re.match(r'^(#{1,6})\s+(.*)', line)
        if m:
            close_list()
            lv = len(m.group(1))
            out.append(f'<h{lv}>{inline(m.group(2))}</h{lv}>')
            i += 1
            continue
        # 分隔线
        if re.match(r'^-{3,}\s*$', stripped):
            close_list()
            out.append('<hr/>')
            i += 1
            continue
        # 引用
        if stripped.startswith('>'):
            close_list()
            out.append(f'<blockquote>{inline(stripped.lstrip(">").strip())}</blockquote>')
            i += 1
            continue
        # 有序列表
        m = re.match(r'^(\d+)\.\s+(.*)', line)
        if m:
            open_list('ol')
            out.append(f'<li>{inline(m.group(2))}</li>')
            i += 1
            continue
        # 无序列表
        m = re.match(r'^[-*]\s+(.*)', line)
        if m:
            open_list('ul')
            out.append(f'<li>{inline(m.group(1))}</li>')
            i += 1
            continue
        # 空行
        if not stripped:
            close_list()
            out.append('')
            i += 1
            continue
        # 段落
        close_list()
        out.append(f'<p>{inline(line)}</p>')
        i += 1
    if in_code:
        out.append('<pre><code>' + html.escape('\n'.join(code_buf)) + '</code></pre>')
    if table_buf:
        out.append(render_table(table_buf))
    close_list()
    return '\n'.join(out)

CSS = """
body { font-family: "Microsoft YaHei","PingFang SC","SimSun",sans-serif; font-size: 12px; line-height: 1.7; color: #2c3e50; margin: 24px; }
h1 { font-size: 22px; color: #1a5276; border-bottom: 3px solid #1a5276; padding-bottom: 8px; margin-top: 28px; }
h2 { font-size: 17px; color: #1a5276; border-bottom: 1.5px solid #aed6f1; padding-bottom: 5px; margin-top: 22px; page-break-after: avoid; }
h3 { font-size: 14.5px; color: #21618c; margin-top: 16px; page-break-after: avoid; }
h4 { font-size: 13px; color: #2e86c1; }
table { border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 11px; page-break-inside: auto; }
th { background: #1a5276; color: #fff; padding: 5px 8px; border: 1px solid #1a5276; text-align: left; }
td { padding: 4px 8px; border: 1px solid #bdc3c7; vertical-align: top; }
tr:nth-child(even) td { background: #f4f6f7; }
code { background: #ecf0f1; padding: 1px 4px; border-radius: 3px; font-family: Consolas,"Courier New",monospace; font-size: 11px; color: #c0392b; }
pre { background: #2c3e50; color: #ecf0f1; padding: 10px 12px; border-radius: 5px; overflow-x: auto; font-size: 10.5px; line-height: 1.5; page-break-inside: avoid; }
pre code { background: none; color: inherit; padding: 0; }
blockquote { border-left: 4px solid #2e86c1; background: #eaf2f8; margin: 8px 0; padding: 6px 12px; color: #1f618d; }
li { margin: 2px 0; }
strong { color: #b03a2e; }
hr { border: none; border-top: 1px dashed #95a5a6; margin: 16px 0; }
p { margin: 6px 0; }
@page { size: A4; margin: 14mm 12mm; }
"""

def main(src, dst_html):
    with io.open(src, 'r', encoding='utf-8') as f:
        text = f.read()
    body = md_to_html(text)
    doc = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<style>{CSS}</style></head><body>
{body}
</body></html>"""
    with io.open(dst_html, 'w', encoding='utf-8') as f:
        f.write(doc)
    print(f"HTML 已生成: {dst_html} ({len(doc)} 字符)")

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
