---
num: 14
title: Собираем игру и сдаём блок
sprint: 2
time: 1 урок
artifact: Готовая змейка, приведённый в порядок файл, защита кода и тег block-2 в репозитории
git: [git tag, git push --tags]
---

## Цель

- Привести файл в порядок, чтобы в нём было легко разбираться.
- Собрать игру целиком и проверить её по списку.
- Пройти защиту кода.
- Отметить конец блока тегом в репозитории.

## Артефакт

Игра работает полностью: управление, еда, рост, смерть, рестарт, ускорение, счёт. Ты можешь объяснить любую строку своего файла.

## Разбор

### Порядок в файле

Сейчас код в файле скорее всего лежит в том порядке, в котором мы его писали. Это нормально, но неудобно: чтобы найти нужную функцию, приходится листать.

Договоримся о порядке, который принят почти везде:

1. **Импорты** — `import pygame`, `import random`.
2. **Настройки** — размеры, скорости, цвета. Всё, что легко поменять, собрано наверху.
3. **Функции** — по смыслу: сначала игровая логика (`new_food`, `new_game`, `move`), потом отрисовка.
4. **Главная функция** — игровой цикл.
5. **Запуск** — одна строка `main()` в самом конце.

Зачем это нужно: настройки не надо искать по всему файлу, а логика отделена от рисования. Если игра тормозит, ты знаешь, что смотреть в отрисовке; если не работает правило — в логике.

### Логика и отрисовка

Обрати внимание, что у нас получилось само собой:

- **логика** — `new_food`, `new_game`, `move`, `direction_from_key`. Работает с клетками, ничего не рисует;
- **отрисовка** — `draw_board`, `draw_snake`, `draw_food`, `draw_score`, `draw_game_over`. Только рисует, ничего не решает.

Такое разделение — не формальность. Через два блока нам понадобится запустить ту же логику для двух игроков сразу. Если правила лежат отдельно от рисования, это будет легко: нарисуем двух змеек, а правила останутся те же.

> [!подсказка]
> Проверь себя: в функции `move` есть хоть одна строка про `screen`? Правильный ответ — нет. Это признак того, что логика чистая.

### Защита кода

На демо я назову любую строку из твоего файла, и ты объяснишь, что она делает и почему стоит именно там. Готовиться не нужно: если ты писал код сам и понимал, что пишешь, ты ответишь. Если копировал не читая — будет видно.

Обычные вопросы:

- почему в проверке границы `>=`, а не `>`;
- почему хвост убирается под условием;
- почему направление меняется на шаге, а не при нажатии;
- что делает `last_move`;
- зачем `pending`, если уже есть `direction`.

## Код

### Файл целиком

Приведи свой файл к такому виду. Если порядок функций у тебя немного другой — не страшно, важно чтобы всё работало и было аккуратно.

```python
import pygame
import random

# ---------- настройки ----------
CELL = 40                 # размер одной клетки в пикселях
COLS = 20                 # сколько клеток по ширине
ROWS = 15                 # сколько клеток по высоте
WIDTH = COLS * CELL
HEIGHT = ROWS * CELL
FPS = 60                  # сколько раз в секунду обновляется экран
START_TICK = 150          # миллисекунд между шагами змейки
MIN_TICK = 60             # быстрее этого змейка не поползёт

# ---------- цвета: три числа (R, G, B), каждое от 0 до 255 ----------
BG_LIGHT = (170, 215, 81)
BG_DARK = (162, 209, 73)
SNAKE_BODY = (60, 90, 200)
SNAKE_HEAD = (40, 60, 160)
FOOD_COLOR = (220, 70, 70)
TEXT_COLOR = (45, 45, 45)

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Змейка")
clock = pygame.time.Clock()
font = pygame.font.Font(None, 30)


def new_food(snake):
    """Случайная свободная клетка поля."""
    free = []
    for x in range(COLS):
        for y in range(ROWS):
            if (x, y) not in snake:
                free.append((x, y))
    if not free:
        return None
    return random.choice(free)


def new_game():
    """Начальное состояние игры."""
    snake = [(COLS // 2, ROWS // 2)]
    direction = (1, 0)
    return snake, direction, new_food(snake), 0, True


def cell_rect(cell):
    """Клетка поля -> прямоугольник на экране."""
    x, y = cell
    return pygame.Rect(x * CELL, y * CELL, CELL, CELL)


def direction_from_key(key, current):
    """Какое направление задаёт клавиша. None — если клавиша не про движение."""
    if key in (pygame.K_UP, pygame.K_w):
        new = (0, -1)
    elif key in (pygame.K_DOWN, pygame.K_s):
        new = (0, 1)
    elif key in (pygame.K_LEFT, pygame.K_a):
        new = (-1, 0)
    elif key in (pygame.K_RIGHT, pygame.K_d):
        new = (1, 0)
    else:
        return None

    # разворот на 180 градусов запрещён
    if (new[0] + current[0], new[1] + current[1]) == (0, 0):
        return None
    return new


def move(snake, direction, food):
    """Один шаг змейки.

    Возвращает новую змейку, съела ли она еду и жива ли.
    """
    head_x, head_y = snake[0]
    dx, dy = direction
    head = (head_x + dx, head_y + dy)

    # упёрлась в стену
    if head[0] < 0 or head[0] >= COLS or head[1] < 0 or head[1] >= ROWS:
        return snake, False, False

    # укусила себя. Последнюю клетку не считаем: хвост в этот же шаг уходит
    if head in snake[:-1]:
        return snake, False, False

    snake = [head] + snake
    ate = head == food
    if not ate:
        snake.pop()
    return snake, ate, True


def draw_board():
    """Шахматное поле."""
    for row in range(ROWS):
        for col in range(COLS):
            if (row + col) % 2 == 0:
                color = BG_LIGHT
            else:
                color = BG_DARK
            pygame.draw.rect(screen, color, cell_rect((col, row)))


def draw_snake(snake):
    for i, cell in enumerate(snake):
        if i == 0:
            color = SNAKE_HEAD
        else:
            color = SNAKE_BODY
        rect = cell_rect(cell)
        pygame.draw.rect(screen, color, rect)
        pygame.draw.rect(screen, BG_DARK, rect, 2)


def draw_food(food):
    if food is None:
        return
    rect = cell_rect(food)
    rect.inflate_ip(-8, -8)
    pygame.draw.ellipse(screen, FOOD_COLOR, rect)


def draw_score(score):
    text = font.render("Счёт: " + str(score), True, TEXT_COLOR)
    screen.blit(text, (10, 8))


def draw_game_over():
    text = font.render("Игра окончена. R — заново", True, TEXT_COLOR)
    rect = text.get_rect(center=(WIDTH // 2, HEIGHT // 2))
    pygame.draw.rect(screen, BG_LIGHT, rect.inflate(30, 20))
    screen.blit(text, rect)


def main():
    snake, direction, food, score, alive = new_game()
    pending = direction          # куда повернём на следующем шаге
    tick = START_TICK            # текущая скорость
    last_move = pygame.time.get_ticks()
    running = True

    while running:
        # 1. ВВОД
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r and not alive:
                    snake, direction, food, score, alive = new_game()
                    pending = direction
                    tick = START_TICK
                    last_move = pygame.time.get_ticks()
                elif alive:
                    new_direction = direction_from_key(event.key, direction)
                    if new_direction is not None:
                        pending = new_direction

        # 2. ОБНОВЛЕНИЕ
        if alive:
            now = pygame.time.get_ticks()
            if now - last_move >= tick:
                last_move = now
                direction = pending
                snake, ate, alive = move(snake, direction, food)
                if ate:
                    score += 1
                    food = new_food(snake)
                    tick = max(MIN_TICK, tick - 5)

        # 3. ОТРИСОВКА
        draw_board()
        draw_food(food)
        draw_snake(snake)
        draw_score(score)
        if not alive:
            draw_game_over()
        pygame.display.flip()

        clock.tick(FPS)

    pygame.quit()


main()
```

## Гит

Отметь конец блока тегом — постоянной меткой на этом снимке:

```
git tag block-2
git push --tags
```

В PyCharm: меню `Git` → `New Tag`, имя `block-2`, затем `Push` с галочкой `Push tags`.

Тег пригодится в декабре: турнирная версия игры будет помечена тегом, и после этого её никто не правит.

## Чек-лист

- [ ] Файл приведён в порядок: настройки сверху, логика и отрисовка раздельно, `main()` в конце
- [ ] Игра запускается и играется до конца
- [ ] Управление работает и стрелками, и WASD
- [ ] Еда появляется, змейка растёт, счёт считается
- [ ] Смерть о стену и о себя работает
- [ ] R начинает новую игру
- [ ] Змейка ускоряется
- [ ] Я могу объяснить любую строку своего файла
- [ ] Тег `block-2` поставлен и отправлен
- [ ] Работа отправлена кнопкой `Push`

## Шпаргалка

### Что должно работать

- Игра играется целиком: управление, еда, рост, смерть, рестарт, ускорение
- Файл приведён в порядок: настройки сверху, логика и отрисовка раздельно
- Тег `block-2` поставлен и отправлен

### Запомнить

- Порядок файла: импорты → настройки → функции → `main()` → запуск.
- **Логика** работает с клетками и ничего не рисует. **Отрисовка** только рисует.
- Такое разделение понадобится, когда в игре появится второй игрок.
- На защите спрашивают по твоему коду: любая строка должна быть понятна.

### Команды

```bash
git tag block-2
git push --tags
```

### Проверьте вместе

Попросите ребёнка объяснить любые две строки из его игры. Если объясняет уверенно — блок пройден.

## Домашка

1. **Пройти викторину по блоку 2:** [[block-2]] — минут на двадцать, с самопроверкой.
2. Добавить рекорд: лучший счёт за всё время работы программы. Подсказка: нужна переменная, которая переживает рестарт — то есть не сбрасывается в `new_game`.
3. Придумать и сделать одно улучшение на выбор: звук при съедании, счёт в заголовке окна, увеличение очков за скорость, новая расцветка.
4. Отправить работу.

## Связи

Назад: [[13]] — рестарт и ускорение. Дальше блок 3: научимся держать в игре двоих игроков — а для этого сначала превратим код в классы.

## Для учителя

- Эталонная версия игры целиком лежит в репозитории курса: `reference/snake.py`. Она проверена запуском: логика, стены, укус себя, заход на хвост, запрет разворота, смерть и рестарт.
- Если кто-то отстал, не давай ему списывать молча. Дай файл и попроси объяснить, что делает каждая функция. Иначе на мультиплеере он встанет окончательно.
- Защита кода — не формальность и не наказание. Она нужна, чтобы к блоку 3 класс пришёл с пониманием своего кода: там предстоит переделывать его в классы.
- Разделение логики и отрисовки стоит проговорить вслух: именно оно позволит на следующем блоке добавить второго игрока без переписывания правил.
