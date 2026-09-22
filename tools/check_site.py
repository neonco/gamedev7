#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка сайта курса. Зависимостей нет, нужен только Python 3.

Что делает:
  1. пересобирает сайт;
  2. сверяет каждый блок кода на странице с исходным Markdown;
  3. ищет неразрешённые перекрёстные ссылки.

Запуск из корня проекта:  python3 tools/check_site.py
"""
from __future__ import annotations

import html
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
LESSONS = ROOT / "content" / "tracks" / "pygame" / "lessons"
QUIZZES = ROOT / "content" / "tracks" / "pygame" / "quizzes"
PAGES = ROOT / "content" / "tracks" / "pygame" / "pages"
DOCS = ROOT / "docs"


def md_code_blocks(path: pathlib.Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        text = text.split("\n---", 1)[1]
    return [m.group(2) for m in re.finditer(r"^```(\w*)\s*\n(.*?)^```\s*$", text, re.S | re.M)]


def html_code_blocks(path: pathlib.Path) -> list[str]:
    raw = re.findall(
        r'<pre translate="no"><code>(.*?)</code></pre>',
        path.read_text(encoding="utf-8"),
        re.S,
    )
    return [html.unescape(re.sub(r"<[^>]+>", "", block)) for block in raw]


def norm(text: str) -> str:
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def check_bracket() -> list[str]:
    """Инварианты жеребьёвки: сетка обязана быть корректной при любом числе участников.

    Ошибка здесь стоит турнира, а не урока, поэтому проверяем отдельно:
    проходы без игры не должны встречаться друг с другом, каждый участник
    обязан попасть в сетку ровно один раз, размер — степень двойки.
    """
    problems: list[str] = []
    sys.path.insert(0, str(ROOT / "tools"))
    import make_bracket  # noqa: E402

    checked = 0
    for count in (2, 3, 5, 7, 8, 13, 16, 20, 24, 31, 32, 40):
        names = [f"игрок {index}" for index in range(1, count + 1)]
        first_round, size, _rounds = make_bracket.build(names, seed=1)
        checked += 1

        if size & (size - 1):
            problems.append(f"сетка на {count}: размер {size} не степень двойки")

        slots = [name for pair in first_round for name in pair if name]
        if len(slots) != count or len(set(slots)) != count:
            problems.append(f"сетка на {count}: участники расставлены неверно")

        if any(left is None and right is None for left, right in first_round):
            problems.append(f"сетка на {count}: два прохода без игры встретились")
    print(f"\nпроверка сетки: вариантов жеребьёвки {checked}")
    return problems


def main() -> int:
    problems: list[str] = []

    build = subprocess.run(
        [sys.executable, str(ROOT / "build.py")], capture_output=True, text=True
    )
    print(build.stdout.strip())
    if build.returncode != 0:
        print(build.stderr.strip(), file=sys.stderr)
        return build.returncode

    pages = [
        DOCS / "index.html",
        *sorted((DOCS / "lesson").glob("*.html")),
        *sorted((DOCS / "quiz").glob("*.html")),
        *sorted((DOCS / "page").glob("*.html")),
    ]

    checked = 0
    pairs = [(md, DOCS / "lesson" / (md.stem + ".html")) for md in sorted(LESSONS.glob("*.md"))]
    pairs += [(md, DOCS / "quiz" / (md.stem + ".html")) for md in sorted(QUIZZES.glob("*.md"))]
    pairs += [(md, DOCS / "page" / (md.stem + ".html")) for md in sorted(PAGES.glob("*.md"))]

    for md, page in pairs:
        if not page.is_file():
            problems.append(f"{md.name}: нет страницы {page.name}")
            continue
        source = md_code_blocks(md)
        rendered = html_code_blocks(page)
        if len(source) != len(rendered):
            problems.append(
                f"{md.name}: блоков кода в Markdown {len(source)}, на странице {len(rendered)}"
            )
            continue
        for i, (a, b) in enumerate(zip(source, rendered), 1):
            checked += 1
            if norm(a) != norm(b):
                problems.append(f"{md.name}, блок {i}: код на странице не совпадает с Markdown")

    # шпаргалка вместо открытых ответов и скрытая методичка
    for md in sorted(LESSONS.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        if "- [?]" in text:
            problems.append(f"{md.name}: остались поля для открытых ответов")
        if "## Шпаргалка" not in text:
            problems.append(f"{md.name}: нет секции «Шпаргалка»")
        if "## Для учителя" not in text:
            problems.append(f"{md.name}: нет секции «Для учителя»")

    for md in sorted(LESSONS.glob("*.md")):
        page = DOCS / "lesson" / (md.stem + ".html")
        if not page.is_file():
            continue
        text = page.read_text(encoding="utf-8")
        if "<details" not in text:
            problems.append(f"{md.name}: методичка не спрятана под спойлер")
        if "data-print-cheat" not in text:
            problems.append(f"{md.name}: нет кнопки печати шпаргалки")
        if 'data-k="' in text and "sheet-row" in text:
            problems.append(f"{md.name}: на странице остались поля для ввода ответов")

    # викторины: у каждого вопроса ровно один верный вариант
    for md in sorted(QUIZZES.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        questions = re.split(r"^## ", text, flags=re.M)[1:]
        for i, question in enumerate(questions, 1):
            right = len(re.findall(r"^\s*-\s*\[[xX]\]", question, re.M))
            options = len(re.findall(r"^\s*-\s*\[[ xX]\]", question, re.M))
            if right != 1:
                problems.append(f"{md.name}, вопрос {i}: верных вариантов {right}, должен быть один")
            if options < 2:
                problems.append(f"{md.name}, вопрос {i}: вариантов ответа меньше двух")

    broken = 0
    for page in pages:
        broken += len(re.findall(r'class="broken"', page.read_text(encoding="utf-8")))
    if broken:
        problems.append(f"неразрешённых перекрёстных ссылок: {broken}")

    print(
        f"\nуроков: {len(list(LESSONS.glob('*.md')))}, "
        f"викторин: {len(list(QUIZZES.glob('*.md')))}, "
        f"документов: {len(list(PAGES.glob('*.md')))}"
    )
    print(f"страниц: {len(pages)}")
    print(f"сверено блоков кода: {checked}")
    print(f"неразрешённых ссылок: {broken}")

    problems += check_bracket()

    if problems:
        print("\nПРОБЛЕМЫ:")
        for problem in problems:
            print("  -", problem)
        return 1
    print("\nсайт в порядке")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
