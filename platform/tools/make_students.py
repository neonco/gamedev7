#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Готовит папки учеников в репозитории класса.

Читает students.txt со строками вида:

    ivan-petrov: Иван Петров
    anna-sidorova: Анна Сидорова

и создаёт для каждого:

    students/<логин>/README.md   личная страница, которую ученик заполняет
    students/<логин>/name.txt    имя для подписи коммитов (читает select-me)

Запуск из папки class-repo:

    python3 make_students.py            # возьмёт students.txt рядом
    python3 make_students.py list.txt   # или другой файл

Повторный запуск безопасен: name.txt обновляется, README.md не затирается,
если ученик уже что-то в нём написал.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "class-repo"
DEFAULT_LIST = ROOT / "students.txt"
LOGIN_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,29}$")

PERSONAL_README = """# {name}

Это моя папка в репозитории класса. Здесь я пишу программы.

## Мои работы

| Урок | Файл | Что работает |
|---|---|---|
|  |  |  |

## Заметки

Что было сложно и как я справился.
"""


def parse(path: Path) -> list[tuple[str, str]]:
    students: list[tuple[str, str]] = []
    seen: set[str] = set()
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            print(f"  строка {number}: нет двоеточия, пропускаю — {line!r}")
            continue
        login, _, name = line.partition(":")
        login = login.strip().lower()
        name = name.strip()
        if not LOGIN_RE.match(login):
            print(f"  строка {number}: плохой логин {login!r} — только латиница, цифры, дефис")
            continue
        if not name:
            print(f"  строка {number}: пустое имя для {login!r}, пропускаю")
            continue
        if login in seen:
            print(f"  строка {number}: логин {login!r} уже был, пропускаю")
            continue
        seen.add(login)
        students.append((login, name))
    return students


def main() -> int:
    if not ROOT.is_dir():
        print(f"Не нашёл папку {ROOT}", file=sys.stderr)
        return 1

    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LIST
    if not src.is_file():
        print(f"Не нашёл список учеников: {src}", file=sys.stderr)
        print("Создай файл со строками вида 'ivan-petrov: Иван Петров'.", file=sys.stderr)
        return 1

    students = parse(src)
    if not students:
        print("Список пустой.", file=sys.stderr)
        return 1

    created = 0
    for login, name in students:
        folder = ROOT / "students" / login
        folder.mkdir(parents=True, exist_ok=True)

        (folder / "name.txt").write_text(name + "\n", encoding="utf-8")

        readme = folder / "README.md"
        if readme.exists():
            print(f"  {login:24} папка есть, README не трогаю")
        else:
            readme.write_text(PERSONAL_README.format(name=name), encoding="utf-8")
            created += 1
            print(f"  {login:24} создан — {name}")

    print(f"\nВсего учеников: {len(students)}, новых папок: {created}")
    print(f"Папка: {ROOT / 'students'}")
    print(
        "\nДальше:\n"
        "  1. Проверь, что в class-repo лежат select-me.cmd, select-me и .gitignore.\n"
        "  2. Закоммить папки учеников и запушь.\n"
        "  3. Перед уроком проверь select-me на тестовой машине.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
