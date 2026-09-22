import array
import math
import pathlib
import wave

import pygame
import random

# ---------- настройки ----------
CELL = 32                 # размер клетки в пикселях
COLS = 28                 # клеток по ширине
ROWS = 18                 # клеток по высоте
WIDTH = COLS * CELL
HEIGHT = ROWS * CELL
FPS = 60
START_TICK = 140          # миллисекунд между шагами
MIN_TICK = 70             # быстрее не поползёт
TICK_STEP = 3             # на сколько ускоряемся за каждую съеденную еду
ROUND_TIME = 90_000       # миллисекунд на раунд
WIN_ROUNDS = 3            # до трёх побед в матче
MAX_ROUNDS = 8            # страховка от бесконечных переигровок при ничьих

# ---------- цвета: три числа (R, G, B) ----------
BG_LIGHT = (170, 215, 81)
BG_DARK = (162, 209, 73)
FOOD_COLOR = (220, 70, 70)
TEXT_COLOR = (45, 45, 45)
PANEL_COLOR = (245, 245, 235)

# направления: вверх, вниз, влево, вправо — в том же порядке, что и клавиши
UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Змейка на двоих")
clock = pygame.time.Clock()
font = pygame.font.Font(None, 30)
big_font = pygame.font.Font(None, 56)


class Snake:
    """Одна змейка. Про другую ничего не знает: правила взаимодействия — в игре."""

    def __init__(self, x, y, direction, keys, color, head_color, name):
        self.body = [(x, y)]
        self.direction = direction
        self.pending = direction
        self.keys = keys                  # (вверх, вниз, влево, вправо)
        self.color = color
        self.head_color = head_color
        self.name = name
        self.alive = True
        self.eaten = 0                    # сколько съела за раунд

    def __len__(self):
        """len(snake) — длина змейки. Python вызывает этот метод сам."""
        return len(self.body)

    def __str__(self):
        """print(snake) покажет состояние: удобно для отладки."""
        return (
            f"{self.name}: длина {len(self.body)}, направление {self.direction}, "
            f"съедено {self.eaten}, жива {self.alive}"
        )

    def turn(self, key):
        """Повернуть, если клавиша про движение и разворот не запрещён."""
        for index, code in enumerate(self.keys):
            if key != code:
                continue
            new = (UP, DOWN, LEFT, RIGHT)[index]
            if (new[0] + self.direction[0], new[1] + self.direction[1]) == (0, 0):
                return
            self.pending = new
            return

    def next_head(self):
        x, y = self.body[0]
        dx, dy = self.pending
        return (x + dx, y + dy)

    def step(self, food, obstacles):
        """Шаг змейки. obstacles — тела других змеек до их хода."""
        head = self.next_head()

        if head[0] < 0 or head[0] >= COLS or head[1] < 0 or head[1] >= ROWS:
            self.alive = False
            return False

        # своё тело без последней клетки: хвост в этот же шаг уходит
        if head in self.body[:-1]:
            self.alive = False
            return False

        for body in obstacles:
            if head in body:
                self.alive = False
                return False

        self.direction = self.pending
        self.body = [head] + self.body
        ate = head == food
        if ate:
            self.eaten += 1
        else:
            self.body.pop()
        return ate

    def draw(self, surface):
        for index, cell in enumerate(self.body):
            if index == 0:
                color = self.head_color
            else:
                color = self.color
            rect = cell_rect(cell)
            pygame.draw.rect(surface, color, rect)
            pygame.draw.rect(surface, BG_DARK, rect, 2)


def cell_rect(cell):
    x, y = cell
    return pygame.Rect(x * CELL, y * CELL, CELL, CELL)


def new_food(snakes):
    """Свободная клетка поля."""
    busy = []
    for snake in snakes:
        busy += snake.body
    free = []
    for x in range(COLS):
        for y in range(ROWS):
            if (x, y) not in busy:
                free.append((x, y))
    if not free:
        return None
    return random.choice(free)


def new_round():
    """Свежие змейки в противоположных концах поля, смотрят друг на друга."""
    player1 = Snake(4, ROWS // 2, RIGHT,
                    (pygame.K_w, pygame.K_s, pygame.K_a, pygame.K_d),
                    (60, 90, 200), (40, 60, 160), "Игрок 1")
    player2 = Snake(COLS - 5, ROWS // 2, LEFT,
                    (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT),
                    (230, 150, 60), (190, 110, 30), "Игрок 2")
    snakes = [player1, player2]
    return snakes, new_food(snakes)


def step_snakes(snakes, food):
    """Один общий шаг обеих змеек.

    Сначала запоминаем тела до хода, чтобы обе змейки играли по одной
    и той же картине поля. Лобовое столкновение убивает обеих.
    """
    bodies = [snake.body for snake in snakes]
    heads = []
    for snake in snakes:
        if snake.alive:
            heads.append(snake.next_head())
        else:
            heads.append(None)

    head_on = heads[0] is not None and heads[0] == heads[1]

    ate = False
    for index, snake in enumerate(snakes):
        if not snake.alive:
            continue
        if head_on:
            snake.alive = False
            continue
        obstacles = [bodies[i] for i in range(len(snakes)) if i != index]
        if snake.step(food, obstacles):
            ate = True
    return ate


def draw_board():
    for row in range(ROWS):
        for col in range(COLS):
            if (row + col) % 2 == 0:
                color = BG_LIGHT
            else:
                color = BG_DARK
            pygame.draw.rect(screen, color, cell_rect((col, row)))


def draw_food(food):
    if food is None:
        return
    rect = cell_rect(food)
    rect.inflate_ip(-8, -8)
    pygame.draw.ellipse(screen, FOOD_COLOR, rect)


SOUND_DIR = pathlib.Path(__file__).resolve().parent / "sounds"


def write_beep(path, frequency, milliseconds, volume=0.35, sample_rate=22050):
    """Записать короткий сигнал в WAV-файл.

    Звук — это последовательность чисел: высота тона задаётся частотой,
    громкость — размахом. Затухание в конце убирает щелчок.
    """
    frames = int(sample_rate * milliseconds / 1000)
    data = array.array("h")
    for i in range(frames):
        value = math.sin(2 * math.pi * frequency * i / sample_rate)
        fade = 1 - i / frames
        data.append(int(value * fade * volume * 32767))
    with wave.open(str(path), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(data.tobytes())


def load_sounds():
    """Загрузить звуки, сгенерировав их при первом запуске.

    Звук не должен ронять игру: если микшера нет или файл не записался,
    возвращаем пустой словарь и играем дальше молча.
    """
    sounds = {}
    try:
        pygame.mixer.init()
        SOUND_DIR.mkdir(exist_ok=True)
        beeps = {
            "eat": (880, 90),
            "crash": (160, 350),
            "win": (660, 400),
        }
        for name, (frequency, milliseconds) in beeps.items():
            path = SOUND_DIR / f"{name}.wav"
            if not path.exists():
                write_beep(path, frequency, milliseconds)
            sounds[name] = pygame.mixer.Sound(str(path))
    except Exception:  # noqa: BLE001 — без звука игра обязана работать
        return {}
    return sounds


def play(sounds, name):
    """Проиграть звук, если он есть."""
    sound = sounds.get(name)
    if sound is not None:
        sound.play()


def draw_hud(snakes, wins, round_number, left_ms):
    """Счёт по раундам, очки за раунд и оставшееся время."""
    line = f"Раунд {round_number}"
    text = font.render(line, True, TEXT_COLOR)
    screen.blit(text, (WIDTH // 2 - text.get_width() // 2, 8))

    seconds = left_ms // 1000
    timer = font.render(f"{seconds:02d}", True, TEXT_COLOR)
    screen.blit(timer, (WIDTH - 46, 8))

    for index, snake in enumerate(snakes):
        name = font.render(
            f"{snake.name}: раунды {wins[index]} · еда {snake.eaten} · длина {len(snake)}",
            True, TEXT_COLOR,
        )
        if index == 0:
            screen.blit(name, (12, HEIGHT - 30))
        else:
            screen.blit(name, (WIDTH - name.get_width() - 12, HEIGHT - 30))


def draw_panel(lines, subtitle=None):
    """Панель по центру экрана: результат раунда, конец матча."""
    height = 40 + len(lines) * 34 + (34 if subtitle else 0)
    panel = pygame.Rect(0, 0, WIDTH - 120, height)
    panel.center = (WIDTH // 2, HEIGHT // 2)
    pygame.draw.rect(screen, PANEL_COLOR, panel)
    pygame.draw.rect(screen, TEXT_COLOR, panel, 2)

    y = panel.top + 20
    for line in lines:
        text = big_font.render(line, True, TEXT_COLOR)
        screen.blit(text, (WIDTH // 2 - text.get_width() // 2, y))
        y += 34
    if subtitle:
        text = font.render(subtitle, True, TEXT_COLOR)
        screen.blit(text, (WIDTH // 2 - text.get_width() // 2, y + 4))


def round_result(snakes):
    """Кто победил в раунде: 0, 1 или None при ничьей."""
    alive = [snake for snake in snakes if snake.alive]
    if len(alive) == 1:
        return snakes.index(alive[0])
    if len(alive) == 2:
        # время вышло, обе живы — решает еда
        if snakes[0].eaten > snakes[1].eaten:
            return 0
        if snakes[1].eaten > snakes[0].eaten:
            return 1
        return None
    # погибли обе — решает еда за раунд
    if snakes[0].eaten > snakes[1].eaten:
        return 0
    if snakes[1].eaten > snakes[0].eaten:
        return 1
    return None


def match_winner(wins, total_eaten):
    """Победитель матча: 0, 1 или None, если решает жребий."""
    if wins[0] > wins[1]:
        return 0
    if wins[1] > wins[0]:
        return 1
    if total_eaten[0] > total_eaten[1]:
        return 0
    if total_eaten[1] > total_eaten[0]:
        return 1
    return None


def main():
    wins = [0, 0]
    total_eaten = [0, 0]
    round_number = 1
    snakes, food = new_round()
    tick = START_TICK
    last_move = pygame.time.get_ticks()
    round_start = last_move
    state = "play"            # play | between | match_over
    result_text = []
    sounds = load_sounds()

    running = True
    while running:
        now = pygame.time.get_ticks()

        # 1. ВВОД
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if state == "play":
                    for snake in snakes:
                        if snake.alive:
                            snake.turn(event.key)
                elif state == "between" and event.key == pygame.K_SPACE:
                    round_number += 1
                    snakes, food = new_round()
                    tick = START_TICK
                    last_move = pygame.time.get_ticks()
                    round_start = last_move
                    state = "play"
                elif state == "match_over" and event.key == pygame.K_r:
                    wins = [0, 0]
                    total_eaten = [0, 0]
                    round_number = 1
                    snakes, food = new_round()
                    tick = START_TICK
                    last_move = pygame.time.get_ticks()
                    round_start = last_move
                    state = "play"

        # 2. ОБНОВЛЕНИЕ
        if state == "play":
            left_ms = ROUND_TIME - (now - round_start)
            if now - last_move >= tick:
                last_move = now
                if step_snakes(snakes, food):
                    play(sounds, "eat")
                    food = new_food(snakes)
                    tick = max(MIN_TICK, tick - TICK_STEP)

            dead = any(not snake.alive for snake in snakes)
            time_up = left_ms <= 0
            if dead or time_up:
                play(sounds, "crash")
                for index, snake in enumerate(snakes):
                    total_eaten[index] += snake.eaten
                winner = round_result(snakes)
                if winner is None:
                    result_text = ["Ничья в раунде", "Раунд переигрывается"]
                else:
                    wins[winner] += 1
                    result_text = [f"{snakes[winner].name} берёт раунд"]

                played = sum(wins) + (1 if winner is None else 0)
                enough = max(wins) >= WIN_ROUNDS
                if enough or played >= MAX_ROUNDS:
                    champion = match_winner(wins, total_eaten)
                    if champion is None:
                        result_text = ["Матч: полная ничья", "Решает жребий"]
                    else:
                        result_text = [f"Матч выиграл {snakes[champion].name}",
                                       f"Раунды {wins[0]} : {wins[1]}"]
                    state = "match_over"
                    play(sounds, "win")
                else:
                    state = "between"
                continue

        # 3. ОТРИСОВКА
        draw_board()
        draw_food(food)
        for snake in snakes:
            snake.draw(screen)
        left_ms = max(0, ROUND_TIME - (now - round_start)) if state == "play" else 0
        draw_hud(snakes, wins, round_number, left_ms)
        if state == "between":
            draw_panel(result_text, "Пробел — следующий раунд")
        elif state == "match_over":
            draw_panel(result_text, "R — новый матч")
        pygame.display.flip()

        clock.tick(FPS)

    pygame.quit()


main()
