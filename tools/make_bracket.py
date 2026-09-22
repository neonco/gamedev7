#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Олимпийская сетка для турнира: жеребьёвка и печатная страница.

    python3 tools/make_bracket.py students.txt
    python3 tools/make_bracket.py students.txt --seed 20261221

Список участников — по одному в строке. Строка вида `ivan-petrov: Иван Петров`
берётся целиком после двоеточия. Строки с решёткой игнорируются.

Что делает:
  * перемешивает участников случайно (seed можно задать — тогда жеребьёвка
    воспроизводима и её можно перепроверить);
  * расставляет проходы без игры так, чтобы они не встретились друг с другом;
  * печатает первый круг в консоль — чтобы прочитать вслух при жеребьёвке;
  * сохраняет самодостаточную страницу turnir/setka.html для печати.

Файл самодостаточный: стили внутри, ничего не подгружает, открывается без
запущенного сервера.
"""
from __future__ import annotations

import argparse
import html
import pathlib
import random
from datetime import date

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "turnir"
OUT = OUT_DIR / "setka.html"

STYLE = """
:root{--fg:#1f2328;--muted:#5b6169;--line:#d8d4cc;--card:#f7f6f2;--accent:#2f7d43}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;color:var(--fg);
  background:#fff;font-size:15px;line-height:1.5;padding:28px 24px 40px;max-width:1400px;margin:0 auto}
h1{font-size:26px;font-weight:650;letter-spacing:-.01em}
h2{font-size:18px;font-weight:650;margin:26px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--line)}
.meta{color:var(--muted);margin-top:6px;font-size:14px}
table{border-collapse:collapse;margin-top:8px;font-size:14px}
th,td{border:1px solid var(--line);padding:5px 12px;text-align:left}
th{background:var(--card);font-weight:600}
.pairs{list-style:none;margin-top:10px;columns:2;column-gap:36px}
.pairs li{padding:5px 0;break-inside:avoid}
.pairs .num{color:var(--muted);display:inline-block;min-width:22px}
.bye{color:var(--accent);font-weight:600}
.rounds{display:flex;gap:14px;align-items:flex-start;overflow-x:auto;padding-bottom:8px}
.round{flex:0 0 210px}
.round h3{font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);
  margin:14px 0 8px;font-weight:700}
.match{border:1px solid var(--line);border-radius:8px;padding:8px 10px;margin-bottom:9px;background:var(--card)}
.match .who{display:block;border-bottom:1px dotted var(--line);padding:3px 0;min-height:24px}
.match .score{color:var(--muted);font-size:12.5px;margin-top:5px}
.match .vs{color:var(--muted);font-size:12px}
footer{margin-top:30px;color:var(--muted);font-size:13px;border-top:1px solid var(--line);padding-top:12px}
@media print{
  body{padding:0;font-size:11pt;max-width:none}
  .rounds{overflow:visible;gap:10px}
  .match{break-inside:avoid}
  h2{break-after:avoid}
}
"""


def read_participants(path: pathlib.Path) -> list[str]:
    names = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            login, _, name = line.partition(":")
            line = name.strip() or login.strip()
        names.append(line)
    return names


def seed_order(size: int) -> list[int]:
    """Стандартный порядок сеяния: 1, size, size/2, ... — проходы не встречаются."""
    order = [1]
    while len(order) < size:
        new_size = len(order) * 2
        folded = []
        for seed in order:
            folded.append(seed)
            folded.append(new_size + 1 - seed)
        order = folded
    return order


def build(names: list[str], seed: int | None):
    rng = random.Random(seed)
    shuffled = names[:]
    rng.shuffle(shuffled)

    size = 1
    while size < len(shuffled):
        size *= 2

    # сеяные номера 1..N — участники, дальше проходы без игры
    by_seed = {number: name for number, name in enumerate(shuffled, start=1)}
    order = seed_order(size)
    slots = [by_seed.get(number) for number in order]

    first_round = [(slots[i], slots[i + 1]) for i in range(0, size, 2)]
    rounds = size.bit_length() - 1
    return first_round, size, rounds


def render(names: list[str], first_round, size: int, rounds: int, seed) -> str:
    pairs = []
    byes = 0
    for number, (left, right) in enumerate(first_round, start=1):
        if right is None:
            byes += 1
            pairs.append(
                f'<li><span class="num">{number}.</span> '
                f"{html.escape(left or '')} — <span class=\"bye\">проходит без игры</span></li>"
            )
        else:
            pairs.append(
                f'<li><span class="num">{number}.</span> '
                f"{html.escape(left or '')} — {html.escape(right or '')}</li>"
            )

    columns = []
    matches_in_round = size // 2
    for round_number in range(1, rounds + 1):
        cards = []
        for match_number in range(1, matches_in_round + 1):
            if round_number == 1:
                left, right = first_round[match_number - 1]
                top = html.escape(left or "—")
                bottom = "проходит без игры" if right is None else html.escape(right or "—")
            else:
                top = f"победитель матча {match_number * 2 - 1}"
                bottom = f"победитель матча {match_number * 2}"
                top = f'<span class="vs">{top}</span>'
                bottom = f'<span class="vs">{bottom}</span>'
            cards.append(
                '<div class="match">'
                f'<span class="who">{top}</span>'
                f'<span class="who">{bottom}</span>'
                '<div class="score">счёт ______ : ______</div>'
                "</div>"
            )
        title = "Первый круг" if round_number == 1 else f"Круг {round_number}"
        columns.append(
            f'<div class="round"><h3>{title}</h3>{"".join(cards)}</div>'
        )
        matches_in_round //= 2

    plan = "".join(
        f"<tr><td>{n}</td><td>{size // (2 ** n)}</td><td>около {10 * n} мин от начала</td></tr>"
        for n in range(1, rounds + 1)
    )

    seed_text = "случайная" if seed is None else f"случайная, seed {seed}"
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Сетка турнира</title>
<style>{STYLE}</style>
</head>
<body>
<h1>Турнир «Змейка на двоих»</h1>
<p class="meta">Участников: {len(names)} · Кругов: {rounds} · Матчей: {len(names) - 1} ·
Проходов без игры: {byes} · Жеребьёвка: {seed_text}</p>

<h2>План дня</h2>
<table>
<tr><th>Круг</th><th>Позиций в сетке</th><th>Ориентир по времени</th></tr>
{plan}
</table>
<p class="meta">Матч — до трёх побед, раунд — до 90 секунд. Круги идут параллельно:
если машин хватает на всех, круг занимает время одного матча. Закладывай час на весь турнир.</p>

<h2>Первый круг</h2>
<ul class="pairs">{"".join(pairs)}</ul>

<h2>Ход турнира</h2>
<div class="rounds">{"".join(columns)}</div>

<footer>
Правила игры и регламент — в материалах курса. Результат матча вписывается сразу
после игры и подтверждается обоими участниками. Дата печати: {date.today():%d.%m.%Y}.
</footer>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Олимпийская сетка для турнира")
    parser.add_argument("participants", help="файл со списком участников")
    parser.add_argument("--seed", type=int, default=None,
                        help="seed жеребьёвки: с ним она воспроизводима")
    args = parser.parse_args()

    path = pathlib.Path(args.participants)
    if not path.is_file():
        print(f"Не нашёл файл со списком участников: {path}")
        return 1

    names = read_participants(path)
    if len(names) < 2:
        print(f"Нужно хотя бы два участника, а в файле {len(names)}.")
        return 1

    seed = args.seed
    if seed is None:
        seed = random.randrange(100000, 999999)

    first_round, size, rounds = build(names, seed)

    print(f"Участников: {len(names)}, кругов: {rounds}, матчей: {size - 1}")
    print(f"Жеребьёвка seed: {seed}  (повторить: --seed {seed})")
    print()
    print("Первый круг:")
    for number, (left, right) in enumerate(first_round, start=1):
        if right is None:
            print(f"  {number:2}. {left} — проходит без игры")
        else:
            print(f"  {number:2}. {left} — {right}")

    OUT_DIR.mkdir(exist_ok=True)
    OUT.write_text(render(names, first_round, size, rounds, seed), encoding="utf-8")
    print()
    print(f"Сетка для печати: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
