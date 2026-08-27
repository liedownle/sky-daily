# -*- coding: utf-8 -*-
"""把探索笔记 Markdown 渲染成带密码门的静态博文页面。

用法：
  python build_blog.py                    # 从 config.json 读取密码，输出 site/index.html
  python build_blog.py --password 我的密码 # 或直接用命令行指定密码
"""
import argparse
import hashlib
import html
import json
import os
import re
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(SCRIPT_DIR, "site", "blog_template.html")
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, "site", "index.html")

BLOG_TITLE = "光遇小精灵每日任务：从抓包到全自动获取"

DEFAULT_SOURCE = os.path.join(SCRIPT_DIR, "blog.md")


def escape(text):
    return html.escape(text, quote=False)


def render_inline(text):
    """行内标记：`code`、**bold**、[text](url)"""
    text = escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def render_table(rows):
    def split_row(r):
        return [c.strip() for c in r.strip().strip("|").split("|")]

    data = [split_row(r) for r in rows if r.strip()]
    data = [r for r in data if not all(set(c) <= set("-:") for c in r)]
    if not data:
        return ""
    head = "".join(f"<th>{render_inline(c)}</th>" for c in data[0])
    body = "".join(
        "<tr>" + "".join(f"<td>{render_inline(c)}</td>" for c in row) + "</tr>"
        for row in data[1:]
    )
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def md_to_html(md):
    lines = md.strip("\n").split("\n")
    out = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]

        # 代码块
        m = re.match(r"^```(\w*)", line)
        if m:
            buf = []
            i += 1
            while i < n and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1  # 跳过结尾 ```
            code = escape("\n".join(buf))
            out.append(f'<pre><code>{code}\n</code></pre>')
            continue

        # 标题
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            level = len(m.group(1))
            out.append(f"<h{level}>{render_inline(m.group(2))}</h{level}>")
            i += 1
            continue

        # 分隔线
        if re.match(r"^\s*---+\s*$", line):
            out.append("<hr>")
            i += 1
            continue

        # 引用
        if line.startswith(">"):
            buf = []
            while i < n and lines[i].startswith(">"):
                buf.append(lines[i][1:].strip())
                i += 1
            content = "<br>".join(render_inline(x) for x in buf)
            out.append(f"<blockquote>{content}</blockquote>")
            continue

        # 无序列表
        if re.match(r"^\s*[-*]\s+", line):
            items = []
            while i < n and re.match(r"^\s*[-*]\s+", lines[i]):
                items.append(f"<li>{render_inline(re.sub(r'^\\s*[-*]\\s+', '', lines[i]))}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue

        # 有序列表
        if re.match(r"^\s*\d+\.\s+", line):
            items = []
            while i < n and re.match(r"^\s*\d+\.\s+", lines[i]):
                items.append(f"<li>{render_inline(re.sub(r'^\\s*\\d+\\.\\s+', '', lines[i]))}</li>")
                i += 1
            out.append("<ol>" + "".join(items) + "</ol>")
            continue

        # 表格
        if line.startswith("|"):
            rows = []
            while i < n and lines[i].startswith("|"):
                rows.append(lines[i])
                i += 1
            out.append(render_table(rows))
            continue

        # 空行
        if not line.strip():
            i += 1
            continue

        # 普通段落（单行）
        out.append(f"<p>{render_inline(line.strip())}</p>")
        i += 1

    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description="生成带密码门的探索笔记博文")
    parser.add_argument("--config", default=os.path.join(SCRIPT_DIR, "config.json"),
                        help="配置文件（读取 site.password，默认 config.json）")
    parser.add_argument("--password", help="直接指定访问密码（优先级最高）")
    parser.add_argument("--source", default=DEFAULT_SOURCE,
                        help=f"博文 Markdown 原文（默认 {DEFAULT_SOURCE}）")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help=f"输出文件（默认 {DEFAULT_OUTPUT}）")
    args = parser.parse_args()

    password = (args.password or "").strip()
    if not password:
        password = (os.environ.get("BLOG_PASSWORD") or "").strip()
    if not password and os.path.exists(args.config):
        try:
            with open(args.config, "r", encoding="utf-8") as f:
                password = ((json.load(f).get("site") or {}).get("password") or "").strip()
        except (json.JSONDecodeError, OSError):
            pass
    if not password:
        print("错误：未提供密码。请用 --password 指定，或在 config.json 的 site.password 中配置。")
        sys.exit(1)

    if not os.path.exists(TEMPLATE):
        print(f"错误：找不到模板 {TEMPLATE}")
        sys.exit(1)
    if not os.path.exists(args.source):
        print(f"错误：找不到博文原文 {args.source}")
        sys.exit(1)

    with open(args.source, "r", encoding="utf-8") as f:
        md = f.read()
    content = md_to_html(md)
    pw_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    meta = ("<span>作者：匿名光之子</span>"
            f"<span>日期：{datetime.now():%Y-%m-%d}</span>"
            "<span>标签：光遇 · 抓包 · 自动化</span>")

    with open(TEMPLATE, "r", encoding="utf-8") as f:
        page = f.read()
    page = (page
            .replace("{{PASSWORD_HASH}}", pw_hash)
            .replace("{{TITLE}}", escape(BLOG_TITLE))
            .replace("{{META}}", meta)
            .replace("{{CONTENT}}", content))

    out_dir = os.path.dirname(args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"[已生成] 博文页面 → {args.output}（密码哈希：{pw_hash[:16]}...）")


if __name__ == "__main__":
    main()
