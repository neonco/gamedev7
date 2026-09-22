#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Генератор сайта курса «Разработка игр, 7 класс».

Контент лежит в content/tracks/<трек>/lessons/*.md — обычный Markdown
с плоским front matter и фиксированными секциями (## Цель, ## Артефакт,
## Разбор, ## Код, ## Гит, ## Чек-лист, ## Рабочий лист, ## Домашка,
## Связи, ## Для учителя).

Запуск:  python3 build.py
Выход:   docs/  (index.html, lesson/<slug>.html, assets/, data/lessons.json)

Только стандартная библиотека. Никаких зависимостей.
"""
from __future__ import annotations

import html
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content" / "tracks"
ASSETS = ROOT / "assets"
OUT = ROOT / "docs"

# Секции, которые рендерятся особым образом. Ключ — название секции
# в нижнем регистре, значение — css-класс и режим обработки.
SECTION_KINDS = {
    "цель": ("goal", "list"),
    "задачи": ("goal", "list"),
    "артефакт": ("artifact", "list"),
    "разбор": ("prose", "md"),
    "теория": ("prose", "md"),
    "код": ("code", "code"),
    "гит": ("git", "code"),
    "git": ("git", "code"),
    "команды": ("git", "code"),
    "чек-лист": ("check", "check"),
    "чеклист": ("check", "check"),
    "шпаргалка": ("cheat", "md"),
    "рабочий лист": ("sheet", "sheet"),
    "домашка": ("home", "md"),
    "домашнее задание": ("home", "md"),
    "связи": ("links", "md"),
    "для учителя": ("teacher", "md"),
}

SECTION_TITLES = {
    "goal": "Цель",
    "artifact": "Артефакт",
    "prose": "Разбор",
    "code": "Код",
    "git": "Гит",
    "check": "Чек-лист",
    "cheat": "Шпаргалка",
    "sheet": "Рабочий лист",
    "home": "Домашка",
    "links": "Связи",
    "teacher": "Для учителя",
}

# ---------------------------------------------------------------- front matter


def split_front_matter(text: str):
    """Плоский front matter между --- в начале файла."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    head = text[3:end].strip("\n")
    body = text[end + 4 :].lstrip("\n")
    meta: dict[str, object] = {}
    for raw in head.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            items = [v.strip().strip("'\"") for v in value[1:-1].split(",")]
            meta[key] = [v for v in items if v]
        else:
            meta[key] = value.strip("'\"")
    return meta, body


# ------------------------------------------------------------------- markdown

PY_KEYWORDS = (
    "False|None|True|and|as|assert|async|await|break|class|continue|def|del|"
    "elif|else|except|finally|for|from|global|if|import|in|is|lambda|nonlocal|"
    "not|or|pass|raise|return|try|while|with|yield"
)
PY_BUILTINS = (
    "print|len|range|int|str|float|list|dict|set|tuple|sorted|sum|min|max|abs|"
    "open|input|enumerate|zip|map|filter|any|all|round|type|isinstance|ord|chr|"
    "bin|hex|oct|pow|divmod|reversed|bool|append|extend|insert|pop|remove|index|"
    "count|sort|split|join|strip|lower|upper|format"
)


def _esc(text: str) -> str:
    return html.escape(text, quote=False)


def highlight_python(code: str) -> str:
    """Подсветка Python регулярками — без внешних библиотек.

    Плейсхолдеры для строк и комментариев помечены буквой S. Без неё
    регулярка подсветки чисел (\\b\\d+\\b) съедает номер плейсхолдера,
    и строки с комментариями пропадают из кода.
    """
    store: list[str] = []

    def stash(match: re.Match) -> str:
        store.append(match.group(0))
        return f"\x00S{len(store) - 1}\x00"

    out = _esc(code)
    out = re.sub(r"(#[^\n]*|f?\"(?:[^\"\\\n]|\\.)*\"|f?'(?:[^'\\\n]|\\.)*')", stash, out)
    out = re.sub(rf"\b({PY_KEYWORDS})\b", r'<span class="k">\1</span>', out)
    out = re.sub(rf"\b({PY_BUILTINS})\b", r'<span class="b">\1</span>', out)
    out = re.sub(r"\b(\d+(?:\.\d+)?)\b", r'<span class="n">\1</span>', out)

    def unstash(match: re.Match) -> str:
        token = store[int(match.group(1))]
        cls = "c" if token.startswith("#") else "s"
        return f'<span class="{cls}">{token}</span>'

    return re.sub(r"\x00S(\d+)\x00", unstash, out)


SHELL_COMMANDS = (
    "git|python|python3|py|pip|cd|ls|dir|mkdir|rm|cp|mv|cls|clear|echo|notepad|"
    "code|explorer|start"
)


def highlight_shell(code: str) -> str:
    lines = []
    for raw in code.split("\n"):
        stripped = raw.strip()
        if stripped.startswith("#"):
            lines.append(f'<span class="c">{_esc(raw)}</span>')
            continue
        store: list[str] = []

        def stash(match: re.Match) -> str:
            store.append(match.group(0))
            return f"\x00S{len(store) - 1}\x00"

        line = _esc(raw)
        line = re.sub(r"('[^']*'|\"[^\"]*\")", stash, line)
        line = re.sub(rf"^(\s*)({SHELL_COMMANDS})\b", r'\1<span class="k">\2</span>', line)
        line = re.sub(r"(\s)(--?[A-Za-z][\w-]*)", r'\1<span class="n">\2</span>', line)
        line = re.sub(
            r"\x00S(\d+)\x00",
            lambda m: f'<span class="s">{store[int(m.group(1))]}</span>',
            line,
        )
        lines.append(line)
    return "\n".join(lines)


def code_block(lang: str, code: str) -> str:
    code = code.rstrip("\n")
    if lang in ("python", "py"):
        body = highlight_python(code)
        label = "python"
    elif lang in ("bash", "sh", "shell", "cmd", "console"):
        body = highlight_shell(code)
        label = "терминал"
    else:
        body = _esc(code)
        label = lang or "текст"
    return (
        '<div class="codeblock">'
        f'<div class="cb-head"><span class="cb-lang">{label}</span>'
        f'<button class="copy" type="button" data-copy>Копировать</button></div>'
        f'<pre translate="no"><code>{body}</code></pre>'
        "</div>"
    )


def _inline(text: str, refs: dict, errors: list[str], where: str) -> str:
    text = _esc(text)
    store: list[str] = []

    def stash(match: re.Match) -> str:
        store.append(match.group(1))
        return f"\x00{len(store) - 1}\x00"

    # код в апострофах защищаем первым
    text = re.sub(r"`([^`]+)`", stash, text)

    # перекрёстные ссылки [[03]] или [[03|текст]]
    def cross(match: re.Match) -> str:
        key, _, label = match.group(1).partition("|")
        key = key.strip()
        target = refs.get(key)
        if target is None:
            errors.append(f"{where}: ссылка [[{key}]] никуда не ведёт")
            return f'<span class="broken" title="нет такого урока">{_esc(label or key)}</span>'
        return f'<a class="cross" href="{target}">{_esc(label.strip() if label else "Урок " + key)}</a>'

    text = re.sub(r"\[\[([^\]]+)\]\]", cross, text)

    # обычные ссылки
    text = re.sub(
        r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
        r'<a href="\2" target="_blank" rel="noopener">\1</a>',
        text,
    )
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", text)

    def unstash(match: re.Match) -> str:
        return f"<code>{store[int(match.group(1))]}</code>"

    return re.sub(r"\x00(\d+)\x00", unstash, text)


CHECK_RE = re.compile(r"^\s*[-*]\s+\[([ xX?])\]\s*(.*)$")
LIST_RE = re.compile(r"^(\s*)[-*]\s+(.*)$")
ORDERED_RE = re.compile(r"^(\s*)\d+[.)]\s+(.*)$")


def render_md(lines: list[str], refs: dict, errors: list[str], where: str, checkbox_ctx: dict | None = None) -> str:
    """Markdown-подмножество: абзацы, списки, чекбоксы, цитаты, код, заголовки."""
    out: list[str] = []
    i = 0
    n = len(lines)
    cb = checkbox_ctx if checkbox_ctx is not None else {"n": 0}

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # блок кода
        fence = re.match(r"^```(\w*)\s*$", stripped)
        if fence:
            lang = fence.group(1)
            buf: list[str] = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append(code_block(lang, "\n".join(buf)))
            continue

        # заголовок
        head = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if head:
            lvl = 2 if len(head.group(1)) <= 2 else min(len(head.group(1)), 5)
            anchor = re.sub(r"[^a-zа-я0-9]+", "-", head.group(2).lower()).strip("-")
            out.append(
                f'<h{lvl} id="{anchor}">{_inline(head.group(2), refs, errors, where)}</h{lvl}>'
            )
            i += 1
            continue

        # цитата / врезка
        if stripped.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].strip())
                i += 1
            kind = "note"
            if buf and buf[0].startswith("[!"):
                close = buf[0].find("]")
                if close > 0:
                    kind = buf[0][2:close].strip().lower()
                    buf[0] = buf[0][close + 1 :].strip()
            body = " ".join(x for x in buf if x)
            out.append(
                f'<div class="callout {kind}">{_inline(body, refs, errors, where)}</div>'
            )
            continue

        # чек-лист или рабочий лист
        if CHECK_RE.match(line):
            items = []
            while i < n and CHECK_RE.match(lines[i]):
                m = CHECK_RE.match(lines[i])
                mark, text = m.group(1), m.group(2)
                key = f"c{cb['n']}"
                cb["n"] += 1
                if mark == "?":
                    items.append(
                        '<li class="sheet-row">'
                        f'<label for="{key}">{_inline(text, refs, errors, where)}</label>'
                        f'<input id="{key}" data-k="{key}" type="text" autocomplete="off">'
                        "</li>"
                    )
                else:
                    checked = " checked" if mark in "xX" else ""
                    items.append(
                        '<li class="check-row">'
                        f'<input id="{key}" data-k="{key}" type="checkbox"{checked}>'
                        f'<label for="{key}">{_inline(text, refs, errors, where)}</label>'
                        "</li>"
                    )
                i += 1
            out.append(f'<ul class="checklist">{"".join(items)}</ul>')
            continue

        # списки
        if LIST_RE.match(line) or ORDERED_RE.match(line):
            ordered = bool(ORDERED_RE.match(line)) and not LIST_RE.match(line)
            items = []
            while i < n and (LIST_RE.match(lines[i]) or ORDERED_RE.match(lines[i])):
                m = ORDERED_RE.match(lines[i]) if ordered else LIST_RE.match(lines[i])
                if not m:
                    break
                items.append(f"<li>{_inline(m.group(2), refs, errors, where)}</li>")
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>{''.join(items)}</{tag}>")
            continue

        # абзац
        buf = []
        while i < n and lines[i].strip() and not re.match(
            r"^(#{1,6}\s|```|>|[-*]\s|\d+[.)]\s)", lines[i].strip()
        ):
            buf.append(lines[i].strip())
            i += 1
        out.append(f"<p>{_inline(' '.join(buf), refs, errors, where)}</p>")

    return "\n".join(out)


# ------------------------------------------------------------------- контент


def split_sections(body: str):
    """Разбивает тело урока на секции по '## Название'."""
    lines = body.split("\n")
    sections: list[tuple[str, list[str]]] = []
    current_title = ""
    current: list[str] = []
    for line in lines:
        if line.startswith("## "):
            if current_title or current:
                sections.append((current_title, current))
            current_title = line[3:].strip()
            current = []
        else:
            current.append(line)
    if current_title or current:
        sections.append((current_title, current))
    return sections


def load_lessons():
    lessons = []
    errors: list[str] = []
    for track_dir in sorted(p for p in CONTENT.iterdir() if p.is_dir()):
        track_meta, track_body = split_front_matter(
            (track_dir / "track.md").read_text(encoding="utf-8")
        )
        lessons_dir = track_dir / "lessons"
        if not lessons_dir.is_dir():
            continue
        for path in sorted(lessons_dir.glob("*.md")):
            meta, body = split_front_matter(path.read_text(encoding="utf-8"))
            slug = path.stem
            sections = split_sections(body)
            lessons.append(
                {
                    "slug": slug,
                    "path": path,
                    "meta": meta,
                    "sections": sections,
                    "track": track_dir.name,
                    "track_meta": track_meta,
                    "track_body": track_body.strip(),
                }
            )
    lessons.sort(key=lambda x: int(x["meta"].get("num", 0)))
    return lessons, errors


def load_quizzes():
    """Викторины по блокам: content/tracks/<трек>/quizzes/*.md."""
    quizzes = []
    for track_dir in sorted(p for p in CONTENT.iterdir() if p.is_dir()):
        quiz_dir = track_dir / "quizzes"
        if not quiz_dir.is_dir():
            continue
        for path in sorted(quiz_dir.glob("*.md")):
            meta, body = split_front_matter(path.read_text(encoding="utf-8"))
            quizzes.append(
                {
                    "slug": path.stem,
                    "path": path,
                    "meta": meta,
                    "questions": split_sections(body),
                    "track": track_dir.name,
                }
            )
    quizzes.sort(key=lambda x: int(x["meta"].get("block", 0)))
    return quizzes


def load_pages():
    """Отдельные страницы трека: правила игры, регламент турнира."""
    pages = []
    for track_dir in sorted(p for p in CONTENT.iterdir() if p.is_dir()):
        pages_dir = track_dir / "pages"
        if not pages_dir.is_dir():
            continue
        for path in sorted(pages_dir.glob("*.md")):
            meta, body = split_front_matter(path.read_text(encoding="utf-8"))
            pages.append(
                {
                    "slug": path.stem,
                    "path": path,
                    "meta": meta,
                    "sections": split_sections(body),
                    "track": track_dir.name,
                }
            )
    pages.sort(key=lambda x: int(x["meta"].get("order", 0)))
    return pages


# --------------------------------------------------------------------- шаблон

HEAD = """<!DOCTYPE html>
<html lang="ru" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#15171a">
<title>{title}</title>
<script>try{{document.documentElement.dataset.theme=(localStorage.getItem('gd7-theme')==='light')?'':'dark';}}catch(e){{document.documentElement.dataset.theme='dark';}}</script>
<link rel="stylesheet" href="{root}assets/site.css">
</head>
<body>
<a class="skip" href="#main">К содержанию</a>
"""

FOOT = """<footer class="site-foot">
  <div class="foot-in">
    <p>Курс «Разработка игр, 7 класс» · материалы собираются из Markdown одной командой <code>python3 build.py</code></p>
  </div>
</footer>
<script src="{root}assets/site.js"></script>
</body>
</html>
"""


def top_bar(root: str, crumbs: str, back: bool = True) -> str:
    left = (
        f'<a class="back" href="{root}index.html">← Карта курса</a>'
        if back
        else '<span class="brand">Разработка игр · 7 класс</span>'
    )
    return (
        '<header class="top"><div class="top-in">'
        f"{left}<span class=\"crumbs\">{crumbs}</span>"
        '<button id="theme" type="button" aria-label="Переключить тему" title="Тема">◐</button>'
        "</div></header>"
    )


def render_sections(sections, refs, errors, where) -> list[str]:
    """Общий рендер секций — используется и уроками, и страницами трека."""
    body: list[str] = []
    cb = {"n": 0}
    for sec_title, sec_lines in sections:
        key = sec_title.strip().lower()
        kind, mode = SECTION_KINDS.get(key, ("prose", "md"))
        sec_id = re.sub(r"[^a-zа-я0-9]+", "-", key).strip("-") or "sec"
        rendered = render_md(
            sec_lines,
            refs,
            errors,
            f"{where} / {sec_title}",
            cb if kind in ("check", "sheet") else None,
        )
        if not rendered.strip():
            continue
        cls = f"sec sec-{kind}"
        head = (
            f'<h2>{SECTION_TITLES.get(kind, sec_title)}</h2>'
            if key in SECTION_KINDS
            else f"<h2>{_esc(sec_title)}</h2>"
        )

        if kind == "cheat":
            head += (
                '<button class="cheat-print" type="button" data-print-cheat>'
                "Распечатать шпаргалку</button>"
            )
            body.append(
                f'<section class="{cls}" id="{sec_id}">{head}'
                f'<div class="cheat-body">{rendered}</div></section>'
            )
        elif kind == "teacher":
            # методичка скрыта, чтобы не попадалась детям на глаза
            body.append(
                f'<details class="{cls}" id="{sec_id}">'
                f'<summary>{SECTION_TITLES.get(kind, sec_title)}</summary>'
                f'<div class="teacher-body">{rendered}</div></details>'
            )
        else:
            body.append(f'<section class="{cls}" id="{sec_id}">{head}{rendered}</section>')
    return body


def render_page(page, refs, errors) -> str:
    """Отдельная страница трека: правила игры, регламент турнира."""
    meta = page["meta"]
    title = meta.get("title", page["slug"])
    note = meta.get("note", "")

    body = render_sections(page["sections"], refs, errors, page["slug"])

    printable = str(meta.get("print", "")).lower() in ("1", "true", "да")
    print_button = (
        '<button class="cheat-print" type="button" data-print-doc>Распечатать</button>'
        if printable
        else ""
    )

    return (
        HEAD.format(title=title, root="../")
        + top_bar("../", "Документ курса")
        + f'<main id="main" class="lesson doc" data-doc="{page["slug"]}">'
        + '<div class="lesson-head">'
        + (f'<div class="lnum">{_esc(note)}</div>' if note else "")
        + f"<h1>{_esc(title)}</h1>"
        + print_button
        + "</div>"
        + "".join(body)
        + "</main>"
        + FOOT.format(root="../")
    )


def render_lesson(lesson, refs, errors, lessons) -> str:
    meta = lesson["meta"]
    num = str(meta.get("num", "")).zfill(2)
    title = meta.get("title", lesson["slug"])
    sprint = meta.get("sprint", "")
    artifact = meta.get("artifact", "")
    git_cmds = meta.get("git", [])
    if isinstance(git_cmds, str):
        git_cmds = [git_cmds]

    body = render_sections(lesson["sections"], refs, errors, lesson["slug"])

    idx = [l["slug"] for l in lessons].index(lesson["slug"])
    prev_l = lessons[idx - 1] if idx > 0 else None
    next_l = lessons[idx + 1] if idx + 1 < len(lessons) else None
    pager = ['<nav class="pager">']
    if prev_l:
        pager.append(
            f'<a class="pill" href="{prev_l["slug"]}.html">← {_esc(str(prev_l["meta"].get("num", "")).zfill(2))} '
            f'{_esc(prev_l["meta"].get("title", ""))}</a>'
        )
    else:
        pager.append('<span class="pill ghost">это первый урок</span>')
    if next_l:
        pager.append(
            f'<a class="pill" href="{next_l["slug"]}.html">{_esc(str(next_l["meta"].get("num", "")).zfill(2))} '
            f'{_esc(next_l["meta"].get("title", ""))} →</a>'
        )
    else:
        pager.append('<span class="pill ghost">это последний урок блока</span>')
    pager.append("</nav>")

    git_badges = "".join(
        f'<code class="cmd">{_esc(c)}</code>' for c in git_cmds if c.strip()
    )

    return (
        HEAD.format(title=f"{num} · {title}", root="../")
        + top_bar("../", f"Спринт {sprint} · Урок {num}")
        + '<main id="main" class="lesson">'
        + '<div class="lesson-head">'
        + f'<div class="lnum">Урок {num}</div>'
        + f"<h1>{_esc(title)}</h1>"
        + (f'<p class="artifact-line"><span>Артефакт</span>{_esc(artifact)}</p>' if artifact else "")
        + (f'<div class="cmds">{git_badges}</div>' if git_badges else "")
        + '<div class="pbar" data-lesson-progress="' + lesson["slug"] + '"><span></span></div>'
        + '<p class="pnote" data-lesson-note="' + lesson["slug"] + '"></p>'
        + "</div>"
        + "\n".join(body)
        + "</main>"
        + "\n".join(pager)
        + FOOT.format(root="../")
    )


def render_question(title, lines, number, refs, errors, where):
    """Один вопрос викторины: текст, варианты, разбор после проверки.

    Варианты записываются как чек-лист: `- [x]` — верный ответ.
    """
    start = next((i for i, line in enumerate(lines) if CHECK_RE.match(line)), None)

    if start is None:
        # вопрос без вариантов — считаем его вопросом «подумай сам»
        body = render_md(lines, refs, errors, f"{where} / {title}")
        return (
            f'<section class="quiz-q open-answer" data-q="{number}">'
            f'<h2>{_inline(title, refs, errors, where)}</h2>{body}</section>'
        )

    end = start
    while end < len(lines) and CHECK_RE.match(lines[end]):
        end += 1

    intro = render_md(lines[:start], refs, errors, f"{where} / {title}")
    tail = render_md(lines[end:], refs, errors, f"{where} / {title}")

    options = []
    for i, line in enumerate(lines[start:end]):
        match = CHECK_RE.match(line)
        mark, text = match.group(1), match.group(2)
        right = ' data-ok="1"' if mark in "xX" else ""
        options.append(
            f'<li><button type="button" class="opt"{right} data-i="{i}">'
            f'<span class="opt-mark" aria-hidden="true"></span>'
            f'<span class="opt-text">{_inline(text, refs, errors, where)}</span>'
            "</button></li>"
        )

    return (
        f'<section class="quiz-q" data-q="{number}">'
        f'<h2><span class="q-num">Вопрос {number}.</span> {_inline(title, refs, errors, where)}</h2>'
        f'<div class="quiz-text">{intro}</div>'
        f'<ul class="quiz-options">{"".join(options)}</ul>'
        f'<div class="quiz-explain" hidden>{tail}</div>'
        "</section>"
    )


def render_quiz(quiz, refs, errors) -> str:
    meta = quiz["meta"]
    title = meta.get("title", quiz["slug"])
    block = meta.get("block", "")
    duration = meta.get("time", "")

    questions = []
    number = 0
    for question_title, question_lines in quiz["questions"]:
        if not question_title.strip():
            continue
        number += 1
        questions.append(
            render_question(question_title, question_lines, number, refs, errors, quiz["slug"])
        )

    return (
        HEAD.format(title=title, root="../")
        + top_bar("../", f"Викторина · блок {block}")
        + f'<main id="main" class="lesson quiz" data-quiz="{quiz["slug"]}">'
        + '<div class="lesson-head">'
        + f'<div class="lnum">Викторина по блоку {_esc(str(block))}</div>'
        + f"<h1>{_esc(title)}</h1>"
        + (
            f'<p class="artifact-line"><span>На дом</span>{_esc(duration)}</p>'
            if duration
            else ""
        )
        + '<p class="quiz-hint">Отметь вариант в каждом вопросе и нажми «Проверить». '
        "Ответы сохраняются в браузере, поэтому викторину можно закрыть и вернуться позже.</p>"
        + "</div>"
        + "".join(questions)
        + '<div class="quiz-actions">'
        + '<button id="quiz-check" type="button" class="primary">Проверить</button>'
        + '<button id="quiz-reset" type="button" class="ghostbtn">Начать заново</button>'
        + '<span id="quiz-score" class="quiz-score" aria-live="polite"></span>'
        + "</div>"
        + "</main>"
        + FOOT.format(root="../")
    )


def render_index(lessons, refs, errors, quizzes=None, pages=None) -> str:
    sprints: dict[str, list] = {}
    for lesson in lessons:
        sprints.setdefault(str(lesson["meta"].get("sprint", "1")), []).append(lesson)

    cards = []
    for sprint in sorted(sprints, key=lambda s: (len(s), s)):
        group = sprints[sprint]
        items = []
        for lesson in group:
            meta = lesson["meta"]
            num = str(meta.get("num", "")).zfill(2)
            git_cmds = meta.get("git", [])
            if isinstance(git_cmds, str):
                git_cmds = [git_cmds]
            badges = "".join(f'<code class="cmd">{_esc(c)}</code>' for c in git_cmds if c.strip())
            items.append(
                '<a class="lcard" '
                f'href="lesson/{lesson["slug"]}.html" '
                f'data-num="{num}" data-title="{_esc(str(meta.get("title", ""))).lower()}" '
                f'data-artifact="{_esc(str(meta.get("artifact", ""))).lower()}" '
                f'data-cmds="{_esc(" ".join(git_cmds)).lower()}" '
                f'data-slug="{lesson["slug"]}">'
                f'<span class="lnum">Урок {num}</span>'
                f'<span class="ltitle">{_esc(meta.get("title", lesson["slug"]))}</span>'
                f'<span class="lart">{_esc(meta.get("artifact", ""))}</span>'
                f'<span class="lcmds">{badges}</span>'
                '<span class="pbar mini" data-lesson-progress="' + lesson["slug"] + '"><span></span></span>'
                "</a>"
            )
        cards.append(
            '<section class="sprint">'
            f'<div class="sprint-head"><h2>Спринт {_esc(sprint)}</h2>'
            f'<span class="scount">{len(group)} ур.</span></div>'
            f'<div class="lgrid">{"".join(items)}</div>'
            "</section>"
        )

    quiz_section = ""
    if quizzes:
        quiz_cards = []
        for quiz in quizzes:
            meta = quiz["meta"]
            seconds = len(quiz["questions"])
            quiz_cards.append(
                f'<a class="lcard quizcard" href="quiz/{quiz["slug"]}.html">'
                f'<span class="lnum">Викторина · блок {_esc(str(meta.get("block", "")))}</span>'
                f'<span class="ltitle">{_esc(meta.get("title", quiz["slug"]))}</span>'
                f'<span class="lart">{seconds} вопросов · {_esc(meta.get("time", ""))}</span>'
                '<span class="lcmds"><code class="cmd">на дом</code></span>'
                "</a>"
            )
        quiz_section = (
            '<section class="sprint quizzes">'
            '<div class="sprint-head"><h2>Викторины по блокам</h2>'
            f'<span class="scount">{len(quizzes)} шт.</span></div>'
            f'<div class="lgrid">{"".join(quiz_cards)}</div>'
            "</section>"
        )

    docs_section = ""
    if pages:
        doc_cards = []
        for doc in pages:
            meta = doc["meta"]
            doc_cards.append(
                f'<a class="lcard doccard" href="page/{doc["slug"]}.html">'
                f'<span class="lnum">{_esc(meta.get("note", "Документ курса"))}</span>'
                f'<span class="ltitle">{_esc(meta.get("title", doc["slug"]))}</span>'
                f'<span class="lart">{_esc(meta.get("summary", ""))}</span>'
                + (
                    '<span class="lcmds"><code class="cmd">можно распечатать</code></span>'
                    if str(meta.get("print", "")).lower() in ("1", "true", "да")
                    else ""
                )
                + "</a>"
            )
        docs_section = (
            '<section class="sprint docs">'
            '<div class="sprint-head"><h2>Документы</h2>'
            f'<span class="scount">{len(pages)} шт.</span></div>'
            f'<div class="lgrid">{"".join(doc_cards)}</div>'
            "</section>"
        )

    track = lessons[0]["track_meta"] if lessons else {}
    title = track.get("title", "Разработка игр, 7 класс")
    subtitle = track.get("subtitle", "")
    artifact = track.get("artifact", "")
    installers = track.get("installers", "")

    intro = ""
    if lessons and lessons[0]["track_body"]:
        intro = (
            '<section class="intro"><div class="intro-in">'
            + render_md(lessons[0]["track_body"].split("\n"), refs, errors, "track")
            + "</div></section>"
        )

    # Ссылка на хранилище с установщиками и QR на саму эту страницу: адрес
    # подставляет браузер, поэтому код ведёт туда, где страница реально открыта.
    actions = ""
    if installers:
        actions = (
            '<div class="hero-actions">'
            f'<a class="btn-primary" href="{_esc(installers)}" target="_blank" rel="noopener">'
            "Скачать установщики</a>"
            '<span class="hero-note">Windows и macOS · Python, PyCharm, pygame-ce, Git</span>'
            "</div>"
        )

    qr = (
        '<aside class="hero-qr">'
        '<div class="qr-box" data-qr></div>'
        '<p class="qr-caption">Наведи камеру телефона,<br>чтобы открыть курс</p>'
        '<code class="qr-url" data-qr-url></code>'
        "</aside>"
    )

    page = (
        HEAD.format(title=title, root="")
        + top_bar("", "", back=False)
        + '<header class="hero"><div class="hero-in">'
        + '<div class="hero-text">'
        + f"<h1>{_esc(title)}</h1>"
        + (f'<p class="sub">{_inline(subtitle, refs, errors, "track")}</p>' if subtitle else "")
        + (f'<p class="final"><span>Главный артефакт</span>{_esc(artifact)}</p>' if artifact else "")
        + actions
        + "</div>"
        + qr
        + "</div></header>"
        + intro
    )

    rest = (
        '<div class="bar"><div class="bar-in">'
        + '<input id="q" type="search" autocomplete="off" spellcheck="false" '
        'placeholder="Поиск: тема, артефакт или команда git…" aria-label="Поиск по курсу">'
        + '<button id="clear" type="button" title="Очистить">×</button>'
        + '<span id="prog" class="prog" aria-live="polite"></span>'
        + '<button id="export" type="button" class="ghostbtn">Выгрузить прогресс</button>'
        + '<label class="ghostbtn file">Загрузить<input id="import" type="file" accept=".json" hidden></label>'
        + "</div></div>"
        + '<main id="main">'
        + '<p class="empty" id="empty">Ничего не найдено. Сбрось запрос.</p>'
        + "".join(cards)
        + quiz_section
        + docs_section
        + "</main>"
        + '<button id="top" type="button" aria-label="Наверх" title="Наверх">↑</button>'
        + FOOT.format(root="")
    )

    # qr.js нужен только на карте курса — грузить его на каждой странице незачем
    rest = rest.replace(
        '<script src="assets/site.js">',
        '<script src="assets/qr.js"></script>\n<script src="assets/site.js">',
    )
    return page + rest


# ----------------------------------------------------------------------- сборка


def main() -> int:
    lessons, errors = load_lessons()
    if not lessons:
        print("Нет уроков в content/tracks/*/lessons/", file=sys.stderr)
        return 1
    quizzes = load_quizzes()
    pages = load_pages()

    # карта ссылок: по номеру и по слагу
    refs: dict[str, str] = {}
    for lesson in lessons:
        target = f"lesson/{lesson['slug']}.html"
        refs[lesson["slug"]] = target
        num = lesson["meta"].get("num")
        if num is not None:
            refs[str(num)] = target
            refs[str(num).zfill(2)] = target
    for quiz in quizzes:
        refs[quiz["slug"]] = f"quiz/{quiz['slug']}.html"
    for page in pages:
        refs[page["slug"]] = f"page/{page['slug']}.html"
    refs["map"] = "index.html"

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "lesson").mkdir(parents=True)
    (OUT / "quiz").mkdir(parents=True)
    (OUT / "page").mkdir(parents=True)
    (OUT / "assets").mkdir(parents=True)
    (OUT / "data").mkdir(parents=True)

    for name in ("site.css", "site.js", "qr.js"):
        shutil.copyfile(ASSETS / name, OUT / "assets" / name)

    (OUT / "index.html").write_text(
        render_index(lessons, refs, errors, quizzes, pages), encoding="utf-8"
    )

    for quiz in quizzes:
        page = OUT / "quiz" / f"{quiz['slug']}.html"
        page.write_text(render_quiz(quiz, refs, errors), encoding="utf-8")

    for doc in pages:
        page = OUT / "page" / f"{doc['slug']}.html"
        page.write_text(render_page(doc, refs, errors), encoding="utf-8")

    payload = []
    for lesson in lessons:
        path = OUT / "lesson" / f"{lesson['slug']}.html"
        path.write_text(render_lesson(lesson, refs, errors, lessons), encoding="utf-8")
        meta = lesson["meta"]
        payload.append(
            {
                "slug": lesson["slug"],
                "num": str(meta.get("num", "")).zfill(2),
                "title": meta.get("title", ""),
                "sprint": str(meta.get("sprint", "")),
                "artifact": meta.get("artifact", ""),
                "git": meta.get("git", []) if isinstance(meta.get("git", []), list) else [meta.get("git")],
                "checks": sum(
                    1
                    for _, lines in lesson["sections"]
                    for line in lines
                    if CHECK_RE.match(line)
                ),
            }
        )
    (OUT / "data" / "lessons.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT / ".nojekyll").write_text("", encoding="utf-8")

    if errors:
        print("Ошибки ссылок:", file=sys.stderr)
        for err in errors:
            print("  -", err, file=sys.stderr)
        return 2

    print(f"OK: {len(lessons)} уроков, {len(quizzes)} викторин, {len(pages)} страниц → {OUT}")
    for lesson in lessons:
        print(f"   {str(lesson['meta'].get('num','')).zfill(2)}  {lesson['meta'].get('title','')}")
    for quiz in quizzes:
        print(f"   викторина блока {quiz['meta'].get('block','')}: {quiz['meta'].get('title','')}")
    for doc in pages:
        print(f"   документ: {doc['meta'].get('title','')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
