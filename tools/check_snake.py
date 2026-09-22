#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка эталонной змейки и полных листингов из уроков.

Нужен pygame (у нас pygame-ce) в том же интерпретаторе:

    python3 -m pip install pygame-ce
    python3 tools/check_snake.py

Что проверяется:
  1. логика move() и direction_from_key() — без окна;
  2. полный прогон игрового цикла с поддельными часами и событиями;
  3. каждый полный листинг из уроков компилируется и запускается без падения.
"""
from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

ROOT = pathlib.Path(__file__).resolve().parent.parent
LESSONS = ROOT / "content" / "tracks" / "pygame" / "lessons"
REFERENCE = ROOT / "reference" / "snake.py"

try:
    import pygame
except ImportError:
    print("Нужен pygame. Установи: python3 -m pip install pygame-ce", file=sys.stderr)
    raise SystemExit(2)

problems: list[str] = []


def check(name: str, got, want) -> None:
    if got != want:
        problems.append(f"{name}: получил {got!r}, ожидал {want!r}")
        print(f"  ПРОВАЛ {name}")
    else:
        print(f"  ок  {name}")


# ---------------------------------------------------------------- эталон


def load_reference() -> dict:
    code = REFERENCE.read_text(encoding="utf-8")
    assert code.rstrip().endswith("main()"), "в эталоне нет вызова main() в конце"
    code = code.rstrip()[: -len("main()")]

    # поддельные часы ставим ДО выполнения: модульный clock возьмёт именно их
    clock_state = {"t": 0}

    class FakeClock:
        def tick(self, fps):
            clock_state["t"] += 20
            return 20

    pygame.time.Clock = FakeClock
    pygame.time.get_ticks = lambda: clock_state["t"]

    namespace: dict = {"__name__": "snake_under_test"}
    exec(compile(code, str(REFERENCE), "exec"), namespace)
    namespace["_clock_state"] = clock_state
    return namespace


def test_logic(ns: dict) -> None:
    move = ns["move"]
    direction_from_key = ns["direction_from_key"]
    cols, rows = ns["COLS"], ns["ROWS"]

    print("\n--- move() ---")
    new, ate, alive = move([(5, 5), (4, 5), (3, 5)], (1, 0), (19, 19))
    check("шаг вправо", new[0], (6, 5))
    check("длина не изменилась", len(new), 3)
    check("хвост ушёл", new[-1], (4, 5))
    check("жива", alive, True)
    check("не съела", ate, False)

    new, ate, alive = move([(5, 5), (4, 5), (3, 5)], (1, 0), (6, 5))
    check("съела еду", ate, True)
    check("выросла", len(new), 4)

    check("смерть о правую стену", move([(cols - 1, 5), (cols - 2, 5)], (1, 0), (0, 0))[2], False)
    check("смерть о верхнюю стену", move([(5, 0), (5, 1)], (0, -1), (0, 0))[2], False)
    check("смерть о нижнюю стену", move([(5, rows - 1), (5, rows - 2)], (0, 1), (0, 0))[2], False)

    body = [(2, 2), (2, 3), (1, 3), (1, 2)]
    check("укус себя", move(body, (0, 1), (9, 9))[2], False)
    check("заход на клетку хвоста разрешён", move(body, (-1, 0), (9, 9))[2], True)

    print("\n--- direction_from_key() ---")
    check("разворот запрещён", direction_from_key(pygame.K_RIGHT, (-1, 0)), None)
    check("поворот разрешён", direction_from_key(pygame.K_UP, (1, 0)), (0, -1))
    check("W = вверх", direction_from_key(pygame.K_w, (1, 0)), (0, -1))
    check("A = влево", direction_from_key(pygame.K_a, (0, -1)), (-1, 0))
    check("S = вниз", direction_from_key(pygame.K_s, (1, 0)), (0, 1))
    check("D = вправо", direction_from_key(pygame.K_d, (0, -1)), (1, 0))
    check("чужая клавиша игнорируется", direction_from_key(pygame.K_SPACE, (1, 0)), None)


def test_full_run(ns: dict) -> None:
    print("\n--- полный прогон игрового цикла ---")
    counters = {"new_game": 0, "game_over": 0}
    real_new_game = ns["new_game"]
    real_game_over = ns["draw_game_over"]

    def counting_new_game():
        counters["new_game"] += 1
        return real_new_game()

    def counting_game_over():
        counters["game_over"] += 1
        return real_game_over()

    ns["new_game"] = counting_new_game
    ns["draw_game_over"] = counting_game_over

    frame = {"n": 0}
    events = {
        5: [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN)],
        20: [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LEFT)],
        200: [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r)],
        260: [pygame.event.Event(pygame.QUIT)],
    }

    def fake_get():
        frame["n"] += 1
        return events.get(frame["n"], [])

    pygame.event.get = fake_get

    try:
        ns["main"]()
    except Exception as exc:  # noqa: BLE001
        problems.append(f"main() упал: {type(exc).__name__}: {exc}")
        print(f"  ПРОВАЛ main() упал — {type(exc).__name__}: {exc}")
        return

    print(f"  ок  отработано кадров: {frame['n']}, игровое время: {ns['_clock_state']['t']} мс")
    check("змейка умирала о стену", counters["game_over"] > 0, True)
    check("игра перезапускалась по R", counters["new_game"] >= 2, True)


# --------------------------------------------------- листинги из уроков


def python_blocks(path: pathlib.Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        text = text.split("\n---", 1)[1]
    return [m.group(1) for m in re.finditer(r"^```python\s*\n(.*?)^```\s*$", text, re.S | re.M)]


def test_lesson_listings() -> None:
    print("\n--- полные листинги из уроков ---")
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="snake-lessons-"))
    found = 0
    for md in sorted(LESSONS.glob("*.md")):
        for i, block in enumerate(python_blocks(md), 1):
            if "pygame.init()" not in block:
                continue  # это фрагмент для вставки, а не программа
            found += 1
            path = tmp / f"{md.stem}-{i}.py"
            path.write_text(block + "\n", encoding="utf-8")

            compiled = subprocess.run(
                [sys.executable, "-m", "py_compile", str(path)],
                capture_output=True, text=True,
                env={**os.environ, "PYTHONPYCACHEPREFIX": str(tmp / "cache")},
            )
            if compiled.returncode != 0:
                problems.append(f"{md.name} блок {i}: не компилируется")
                print(f"  ПРОВАЛ компиляции {md.name} блок {i}")
                continue

            run = subprocess.Popen(
                [sys.executable, str(path)], cwd=str(tmp),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=os.environ,
            )
            try:
                _, err = run.communicate(timeout=4)
                crashed = run.returncode != 0
            except subprocess.TimeoutExpired:
                run.kill()
                _, err = run.communicate()
                crashed = "Traceback" in (err or "")
            if crashed:
                problems.append(f"{md.name} блок {i}: падает при запуске")
                print(f"  ПРОВАЛ запуска {md.name} блок {i}")
            else:
                print(f"  ок  {md.name} блок {i}")
    print(f"  всего полных программ: {found}")


TWO_PLAYER = ROOT / "reference" / "snake2.py"


def load_two_players() -> dict:
    """Эталон змейки на двоих. Часы подменяются до выполнения файла."""
    code = TWO_PLAYER.read_text(encoding="utf-8")
    assert code.rstrip().endswith("main()"), "в эталоне на двоих нет вызова main() в конце"
    code = code.rstrip()[: -len("main()")]
    namespace: dict = {"__name__": "snake2_under_test", "__file__": str(TWO_PLAYER)}
    exec(compile(code, str(TWO_PLAYER), "exec"), namespace)
    return namespace


def test_two_players(ns: dict) -> None:
    Snake = ns["Snake"]
    step_snakes = ns["step_snakes"]
    round_result = ns["round_result"]
    match_winner = ns["match_winner"]
    new_round = ns["new_round"]
    up, down, left, right = ns["UP"], ns["DOWN"], ns["LEFT"], ns["RIGHT"]
    cols, rows = ns["COLS"], ns["ROWS"]

    def make(x, y, direction=right, eaten=0):
        keys = (pygame.K_w, pygame.K_s, pygame.K_a, pygame.K_d)
        snake = Snake(x, y, direction, keys, (1, 2, 3), (4, 5, 6), "тест")
        snake.eaten = eaten
        return snake

    print("\n--- змейка на двоих: шаг ---")
    snake = make(5, 5)
    snake.body = [(5, 5), (4, 5), (3, 5)]
    snake.step((20, 20), [])
    check("шаг вправо", snake.body[0], (6, 5))
    check("длина та же", len(snake.body), 3)

    snake = make(5, 5)
    snake.body = [(5, 5), (4, 5)]
    snake.step((6, 5), [])
    check("съела и выросла", (snake.eaten, len(snake.body)), (1, 3))

    snake = make(cols - 1, 5)
    snake.step((0, 0), [])
    check("смерть о стену", snake.alive, False)

    snake = make(2, 2, down)
    snake.body = [(2, 2), (2, 3), (1, 3), (1, 2)]
    snake.step((20, 20), [])
    check("укус себя", snake.alive, False)

    snake = make(2, 2, left)
    snake.body = [(2, 2), (2, 3), (1, 3), (1, 2)]
    snake.step((20, 20), [])
    check("заход на свой хвост разрешён", snake.alive, True)

    snake = make(5, 5)
    snake.step((20, 20), [[(6, 5)]])
    check("смерть о чужое тело", snake.alive, False)

    print("\n--- поворот ---")
    snake = make(5, 5, right)
    snake.turn(pygame.K_w)
    check("W поворачивает вверх", snake.pending, up)
    snake = make(5, 5, right)
    snake.turn(pygame.K_a)
    check("разворот запрещён", snake.pending, right)
    snake = make(5, 5, right)
    snake.turn(pygame.K_UP)
    check("чужие клавиши не действуют", snake.pending, right)

    print("\n--- правила взаимодействия ---")
    alive1, dead2 = make(5, 5), make(20, 5)
    dead2.alive = False
    check("победа по выживанию", round_result([alive1, dead2]), 0)
    both_dead_a, both_dead_b = make(5, 5, right, eaten=2), make(20, 5, left, eaten=1)
    both_dead_a.alive = False
    both_dead_b.alive = False
    check("обе погибли — решает еда", round_result([both_dead_a, both_dead_b]), 0)
    both_dead_a.eaten = 1
    check("обе погибли, еда поровну — ничья", round_result([both_dead_a, both_dead_b]), None)
    check("матч по раундам", match_winner([2, 0], [1, 5]), 0)
    check("матч по еде", match_winner([2, 2], [1, 5]), 1)
    check("полная ничья", match_winner([2, 2], [3, 3]), None)

    print("\n--- лоб в лоб ---")
    first, second = make(5, 5, right), make(6, 5, left)
    step_snakes([first, second], (20, 20))
    check("погибли обе", [first.alive, second.alive], [False, False])

    print("\n--- новая расстановка ---")
    snakes, food = new_round()
    check("смотрят друг на друга", (snakes[0].direction, snakes[1].direction), (right, left))
    check("стартуют в одной строке", snakes[0].body[0][1], snakes[1].body[0][1])
    check("еда вне змеек", food in [c for s in snakes for c in s.body], False)

    print("\n--- магические методы ---")
    snake = make(5, 5)
    snake.body = [(5, 5), (4, 5), (3, 5)]
    check("len(snake) — длина тела", len(snake), 3)
    snake.eaten = 2
    text = str(snake)
    check("str(snake) содержит имя", "тест" in text, True)
    check("str(snake) содержит длину", "длина 3" in text, True)
    check("str(snake) содержит съеденное", "съедено 2" in text, True)

    print("\n--- звук ---")
    sounds = ns["load_sounds"]()
    check("звуки сгенерированы и загружены", sorted(sounds.keys()), ["crash", "eat", "win"])
    sound_files = sorted(p.name for p in (TWO_PLAYER.parent / "sounds").glob("*.wav"))
    check("файлы звуков лежат рядом с эталоном", sound_files, ["crash.wav", "eat.wav", "win.wav"])
    play_sound = ns["play"]
    play_sound(sounds, "eat")
    play_sound({}, "eat")
    play_sound(sounds, "нет такого звука")
    print("  ок  отсутствие звука игру не роняет")

    print("\n--- полный матч ---")
    panels: list = []
    real_panel = ns["draw_panel"]

    def spy_panel(lines, subtitle=None):
        panels.append(" | ".join(lines))
        return real_panel(lines, subtitle)

    ns["draw_panel"] = spy_panel
    frame = {"n": 0}
    events = {
        5: [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_w)],
        80: [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)],
        85: [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_w)],
        170: [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)],
        175: [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_w)],
        260: [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)],
        265: [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_w)],
        400: [pygame.event.Event(pygame.QUIT)],
    }

    def scripted():
        frame["n"] += 1
        if frame["n"] > 500:
            return [pygame.event.Event(pygame.QUIT)]
        return events.get(frame["n"], [])

    pygame.event.get = scripted
    try:
        ns["main"]()
    except Exception as exc:  # noqa: BLE001
        problems.append(f"матч на двоих упал: {type(exc).__name__}: {exc}")
        print(f"  ПРОВАЛ матч упал — {type(exc).__name__}: {exc}")
    else:
        print(f"  ок  матч отработал {frame['n']} кадров")
    check("раунд достался игроку 2", any("Игрок 2 берёт раунд" in t for t in panels), True)
    check("матч до трёх побед завершён", any("Матч выиграл Игрок 2" in t for t in panels), True)


def main() -> int:
    ns = load_reference()
    test_logic(ns)
    test_full_run(ns)
    test_lesson_listings()
    test_two_players(load_two_players())

    print()
    if problems:
        print("ПРОБЛЕМЫ:")
        for problem in problems:
            print("  -", problem)
        return 1
    print("всё в порядке")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
