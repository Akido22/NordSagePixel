"""Постройки и убранство города, нарисованные примитивами Pyxel.

Каждый реквизит задаётся в разделе [props] файла уровня:
    вид  столбец,строка  [ширина_в_тайлах]
(столбец, строка) — левый нижний тайл, на котором стоит постройка.
"""

import math
import random

import pyxel

from . import ui
from .config import TILE


class Prop:
    def __init__(self, kind, tx, ty, w_tiles=0):
        self.kind = kind
        self.x = tx * TILE
        self.base = (ty + 1) * TILE
        self.w = (w_tiles or _DEFAULT_W.get(kind, 2)) * TILE
        self.seed = tx * 31 + ty * 7

    @property
    def front(self):
        """Рисовать ли поверх героя (фонари и стяги — нет, всё остальное позади)."""
        return False

    def update(self, world):
        t = pyxel.frame_count
        if self.kind == "izba" and t % 18 == self.seed % 18:
            world.puff(self.x + self.w - 14, self.base - 64)
        elif self.kind == "forge":
            if t % 10 == self.seed % 10:
                world.puff(self.x + 10, self.base - 52)
            if t % 50 == 0:  # кузнец бьёт по наковальне
                world.sparks(self.x + self.w - 22, self.base - 12, 5)

    def draw(self):
        _DRAW[self.kind](self)


# ---------------------------------------------------------------- изба
def _window(x, y, lit=True):
    """Окно с резным наличником и ставнями."""
    t = pyxel.frame_count
    pyxel.rect(x - 4, y - 1, 3, 10, 8)  # ставни
    pyxel.rect(x + 9, y - 1, 3, 10, 8)
    pyxel.line(x - 3, y + 1, x - 3, y + 6, 10)
    pyxel.line(x + 10, y + 1, x + 10, y + 6, 10)
    glow = 10 if lit and (t // 40 + x) % 7 else 9
    pyxel.rect(x, y, 8, 8, glow if lit else 1)
    pyxel.line(x + 4, y, x + 4, y + 7, 2)
    pyxel.line(x, y + 4, x + 7, y + 4, 2)
    pyxel.rectb(x - 1, y - 1, 10, 10, 7)
    pyxel.tri(x - 2, y - 2, x + 4, y - 7, x + 10, y - 2, 7)  # «кокошник» наличника
    pyxel.pset(x + 4, y - 4, 8)
    pyxel.line(x - 2, y + 9, x + 10, y + 9, 7)
    pyxel.pset(x + 1, y + 10, 7)
    pyxel.pset(x + 4, y + 10, 7)
    pyxel.pset(x + 7, y + 10, 7)


def _log_wall(x, y, w, h):
    pyxel.rect(x, y, w, h, 4)
    for yy in range(y + 3, y + h, 4):
        pyxel.line(x, yy, x + w - 1, yy, 2)
    # Выпуски брёвен на углах.
    for yy in range(y, y + h, 4):
        pyxel.rect(x - 2, yy, 3, 3, 4)
        pyxel.rect(x + w - 1, yy, 3, 3, 4)
        pyxel.pset(x - 2, yy + 1, 2)
        pyxel.pset(x + w + 1, yy + 1, 2)


def _draw_izba(p):
    x, b, w = p.x, p.base, p.w
    wall_h = 36
    top = b - wall_h
    # Труба.
    pyxel.rect(x + w - 17, top - 26, 6, 14, 5)
    pyxel.rect(x + w - 18, top - 27, 8, 2, 6)
    _log_wall(x + 4, top, w - 8, wall_h)
    # Фронтон.
    apex = (x + w // 2, top - 24)
    pyxel.tri(x - 2, top + 1, apex[0], apex[1], x + w + 1, top + 1, 2)
    pyxel.tri(x + 4, top, apex[0], apex[1] + 5, x + w - 5, top, 4)
    for i in range(1, 5):
        yy = top - i * 5
        half = (yy - apex[1] - 5) * (w // 2 - 9) / 19
        if half > 0:
            pyxel.line(apex[0] - half, yy, apex[0] + half, yy, 2)
    # Резные причелины по краю крыши.
    pyxel.line(x - 2, top + 1, apex[0], apex[1], 7)
    pyxel.line(x + w + 1, top + 1, apex[0], apex[1], 7)
    for i in range(1, 6):
        k = i / 6
        px = x - 2 + (apex[0] - x + 2) * k
        py = top + 1 + (apex[1] - top - 1) * k
        pyxel.pset(px, py + 2, 8)
        pyxel.pset(x + w + 1 - (x + w + 1 - apex[0]) * k, py + 2, 8)
    # Конёк-охлупень.
    ax, ay = apex
    pyxel.line(ax, ay, ax, ay - 4, 2)
    pyxel.line(ax, ay - 4, ax + 4, ay - 6, 2)
    pyxel.line(ax + 4, ay - 6, ax + 6, ay - 4, 2)
    pyxel.pset(ax + 3, ay - 5, 7)
    pyxel.line(ax, ay - 1, ax - 3, ay + 1, 2)
    # Слуховое окно светёлки.
    pyxel.circ(ax, top - 9, 3, 1)
    pyxel.circb(ax, top - 9, 3, 7)
    pyxel.pset(ax, top - 9, 9)
    # Окна.
    n = max(1, (w - 16) // 22)
    gap = (w - 8) / (n + 1)
    for i in range(n):
        _window(int(x + 4 + gap * (i + 1) - 4), top + 10)
    # Завалинка.
    pyxel.rect(x + 2, b - 3, w - 4, 3, 2)


# ---------------------------------------------------------------- длинный дом
def _draw_longhouse(p):
    x, b, w = p.x, p.base, p.w
    wall_h = 24
    top = b - wall_h
    pyxel.rect(x + 6, top, w - 12, wall_h, 2)
    for xx in range(x + 8, x + w - 7, 4):
        pyxel.line(xx, top, xx, b - 1, 4)
    # Дёрновая крыша.
    rt = top - 26
    pyxel.tri(x - 2, top + 2, x + 18, rt, x + 18, top + 2, 3)
    pyxel.tri(x + w + 1, top + 2, x + w - 19, rt, x + w - 19, top + 2, 3)
    pyxel.rect(x + 18, rt, w - 36, top - rt + 2, 3)
    pyxel.line(x + 18, rt, x + w - 19, rt, 11)
    pyxel.line(x - 2, top + 2, x + 18, rt, 11)
    pyxel.line(x + w + 1, top + 2, x + w - 19, rt, 11)
    for i in range(0, w - 40, 7):
        pyxel.pset(x + 20 + i, rt + 3 + (i * 3) % 7, 11)
        pyxel.pset(x + 22 + i, rt + 10 + (i * 5) % 9, 11)
    pyxel.line(x - 2, top + 2, x + w + 1, top + 2, 2)
    # Драконьи головы на концах конька.
    for sx, d in ((x + 18, -1), (x + w - 19, 1)):
        pyxel.line(sx, rt, sx + d * 6, rt - 8, 4)
        pyxel.line(sx + d * 6, rt - 8, sx + d * 9, rt - 8, 4)
        pyxel.line(sx + d * 9, rt - 8, sx + d * 9, rt - 6, 4)
        pyxel.pset(sx + d * 7, rt - 9, 8)
    # Дверь с резьбой.
    dx = x + w // 2 - 6
    pyxel.rect(dx, b - 18, 12, 18, 1)
    pyxel.rectb(dx - 1, b - 19, 14, 19, 4)
    pyxel.line(dx + 6, b - 18, dx + 6, b - 1, 2)
    ui.rhombus(dx + 6, b - 23, 2, 10)
    # Щиты на стене.
    colors = [(10, 8, 10), (7, 12, 7), (2, 10, 2), (10, 3, 10)]
    i = 0
    for sx in range(x + 14, x + w - 12, 14):
        if abs(sx - (dx + 6)) < 14:
            continue
        rim, body, boss = colors[i % len(colors)]
        pyxel.circ(sx, b - 14, 5, body)
        pyxel.circb(sx, b - 14, 5, rim)
        pyxel.line(sx - 4, b - 14, sx + 4, b - 14, rim)
        pyxel.circ(sx, b - 14, 1, boss)
        i += 1


# ---------------------------------------------------------------- кузница
def _draw_forge(p):
    x, b, w = p.x, p.base, p.w
    t = pyxel.frame_count
    # Задняя стена и горн.
    pyxel.rect(x + 2, b - 34, w - 4, 34, 1)
    pyxel.rect(x + 4, b - 22, 16, 22, 5)
    pyxel.rectb(x + 4, b - 22, 16, 22, 6)
    pyxel.rect(x + 7, b - 52, 10, 30, 5)  # дымоход
    pyxel.rect(x + 6, b - 53, 12, 2, 6)
    pyxel.rect(x + 7, b - 16, 10, 8, 0)
    for i in range(6):
        fx = x + 8 + (i * 3 + t // 4) % 8
        fy = b - 10 - ((t // 3 + i * 5) % 6)
        pyxel.pset(fx, fy, 10 if i % 2 else 9)
    pyxel.rect(x + 8, b - 10, 8, 2, 8)
    pyxel.dither(0.07 + 0.03 * math.sin(t * 0.3))
    pyxel.circ(x + 12, b - 12, 11, 9)
    pyxel.dither(1.0)
    # Инструмент на стене.
    for i, tx in enumerate(range(x + 26, x + w - 8, 6)):
        pyxel.line(tx, b - 30, tx, b - 22, 4)
        pyxel.rect(tx - 1, b - 31, 3, 2 + i % 2, 6)
    # Навес на столбах.
    pyxel.rect(x + 1, b - 34, 3, 34, 4)
    pyxel.rect(x + w - 4, b - 34, 3, 34, 4)
    pyxel.tri(x - 4, b - 33, x + w + 3, b - 33, x + w + 3, b - 42, 2)
    pyxel.tri(x - 4, b - 33, x - 4, b - 38, x + w + 3, b - 42, 2)
    pyxel.line(x - 4, b - 33, x + w + 3, b - 33, 4)
    # Наковальня на чурбаке.
    ax = x + w - 24
    pyxel.rect(ax, b - 6, 6, 6, 4)
    pyxel.rect(ax - 2, b - 10, 10, 4, 6)
    pyxel.rect(ax - 4, b - 10, 3, 2, 6)
    pyxel.line(ax - 2, b - 10, ax + 7, b - 10, 15)
    pyxel.rect(ax + 1, b - 11, 3, 1, 9 if (t // 50) % 2 else 6)  # раскалённая заготовка


# ---------------------------------------------------------------- колодец
def _draw_well(p):
    x, b = p.x, p.base
    pyxel.rect(x + 1, b - 12, 18, 12, 4)
    for yy in range(b - 9, b, 3):
        pyxel.line(x + 1, yy, x + 18, yy, 2)
    pyxel.rectb(x + 1, b - 12, 18, 12, 2)
    pyxel.rect(x + 2, b - 30, 2, 18, 2)
    pyxel.rect(x + 16, b - 30, 2, 18, 2)
    pyxel.tri(x - 2, b - 29, x + 10, b - 38, x + 22, b - 29, 2)
    pyxel.tri(x + 1, b - 30, x + 10, b - 36, x + 19, b - 30, 4)
    pyxel.line(x + 3, b - 24, x + 17, b - 24, 4)  # ворот
    pyxel.line(x + 10, b - 24, x + 10, b - 17, 6)
    pyxel.rect(x + 8, b - 17, 5, 4, 5)
    pyxel.line(x + 17, b - 24, x + 20, b - 22, 2)


# ---------------------------------------------------------------- торговая лавка
def _draw_stall(p):
    x, b, w = p.x, p.base, p.w
    rnd = random.Random(p.seed)
    pyxel.rect(x + 2, b - 30, 2, 30, 2)
    pyxel.rect(x + w - 4, b - 30, 2, 30, 2)
    # Прилавок с товаром.
    pyxel.rect(x + 1, b - 12, w - 2, 3, 4)
    pyxel.rect(x + 3, b - 9, w - 6, 9, 2)
    gx = x + 4
    while gx < x + w - 8:
        kind = rnd.randrange(4)
        if kind == 0:  # горшок
            pyxel.circ(gx + 3, b - 15, 3, 9)
            pyxel.rect(gx + 2, b - 19, 3, 1, 2)
        elif kind == 1:  # каравай
            pyxel.elli(gx, b - 16, 8, 4, 9)
            pyxel.pset(gx + 3, b - 15, 10)
        elif kind == 2:  # свёрток ткани
            pyxel.rect(gx, b - 17, 7, 5, rnd.choice((8, 12, 7)))
            pyxel.line(gx, b - 15, gx + 6, b - 15, 10)
        else:  # кувшин
            pyxel.rect(gx + 1, b - 18, 4, 6, 4)
            pyxel.rect(gx + 2, b - 20, 2, 2, 4)
        gx += 9
    # Полосатый навес.
    for i, xx in enumerate(range(x - 2, x + w + 2, 4)):
        col = 8 if i % 2 == 0 else 7
        pyxel.rect(xx, b - 36, 4, 7, col)
        pyxel.tri(xx, b - 29, xx + 3, b - 29, xx + 1.5, b - 27, col)
    pyxel.line(x - 2, b - 36, x + w + 1, b - 36, 2)


# ---------------------------------------------------------------- стяг
def _draw_banner(p):
    x, b = p.x + 3, p.base
    t = pyxel.frame_count
    pyxel.rect(x, b - 48, 2, 48, 2)
    pyxel.tri(x - 1, b - 48, x + 3, b - 48, x + 1, b - 53, 10)
    pyxel.line(x - 6, b - 46, x + 7, b - 46, 4)
    for i in range(12):
        sway = int(math.sin(t * 0.06 + i * 0.35) * 1.5)
        cx = x - 5 + i
        pyxel.line(cx + sway * 0, b - 45 + sway, cx, b - 25 + sway + (i % 2) * 2, 8)
    sway = int(math.sin(t * 0.06 + 2) * 1.5)
    ui.rhombus(x + 1, b - 36 + sway, 3, 10)
    pyxel.pset(x + 1, b - 36 + sway, 8)


# ---------------------------------------------------------------- фонарь
def _draw_lantern(p):
    x, b = p.x + 3, p.base
    t = pyxel.frame_count
    pyxel.rect(x, b - 26, 2, 26, 2)
    pyxel.line(x - 2, b - 26, x + 3, b - 26, 2)
    pyxel.rectb(x - 2, b - 33, 6, 7, 2)
    flick = (t // 5 + p.seed) % 3
    pyxel.rect(x - 1, b - 32, 4, 5, 9 if flick else 10)
    pyxel.pset(x, b - 31, 10)
    pyxel.tri(x - 3, b - 33, x + 1, b - 37, x + 4, b - 33, 2)
    pyxel.dither(0.05 + 0.02 * flick)
    pyxel.circ(x + 1, b - 30, 9, 10)
    pyxel.dither(1.0)


# ---------------------------------------------------------------- плетень
def _draw_fence(p):
    x, b, w = p.x, p.base, p.w
    for sx in range(x + 1, x + w, 8):
        pyxel.rect(sx, b - 14, 2, 14, 2)
        pyxel.pset(sx, b - 15, 2)
    for row in range(3):
        y = b - 12 + row * 4
        for xx in range(x, x + w, 2):
            off = 1 if ((xx - x) // 8 + row) % 2 else 0
            pyxel.pset(xx, y + off, 4)
            pyxel.pset(xx + 1, y + off, 4)


# ---------------------------------------------------------------- дуб
def _draw_oak(p):
    x, b = p.x + 8, p.base
    pyxel.rect(x - 4, b - 34, 9, 34, 2)
    pyxel.line(x - 2, b - 30, x - 2, b - 4, 4)
    pyxel.tri(x - 8, b, x - 4, b - 8, x - 4, b, 2)
    pyxel.tri(x + 9, b, x + 4, b - 8, x + 4, b, 2)
    pyxel.line(x, b - 30, x - 12, b - 40, 2)
    pyxel.line(x + 2, b - 28, x + 14, b - 38, 2)
    for cx, cy, r, col in ((x, b - 50, 17, 3), (x - 15, b - 42, 11, 3), (x + 15, b - 42, 11, 3),
                           (x - 3, b - 55, 12, 11), (x - 14, b - 45, 6, 11), (x + 12, b - 46, 7, 11)):
        pyxel.circ(cx, cy, r, col)
    # Обережные ленты на ветвях.
    t = pyxel.frame_count
    for i, (lx, ly, col) in enumerate(((x - 11, b - 38, 8), (x + 12, b - 36, 7), (x + 5, b - 33, 8))):
        sway = int(math.sin(t * 0.05 + i) * 1.2)
        pyxel.line(lx, ly, lx + sway, ly + 7, col)


# ---------------------------------------------------------------- бочки и ящики
def _draw_barrels(p):
    x, b = p.x, p.base
    for i, bx in enumerate((x, x + 9)):
        pyxel.rect(bx + 1, b - 11, 7, 11, 4)
        pyxel.line(bx, b - 9, bx, b - 2, 4)
        pyxel.line(bx + 8, b - 9, bx + 8, b - 2, 4)
        pyxel.line(bx, b - 9, bx + 8, b - 9, 5)
        pyxel.line(bx, b - 3, bx + 8, b - 3, 5)
    pyxel.rect(x + 3, b - 19, 10, 8, 4)
    pyxel.rectb(x + 3, b - 19, 10, 8, 2)
    pyxel.line(x + 3, b - 19, x + 12, b - 12, 2)


# ---------------------------------------------------------------- частокол с башней
def _draw_wall(p):
    x, b, w = p.x, p.base, p.w
    for sx in range(x, x + w, 4):
        h = 56 + (sx // 4) % 2 * 2
        pyxel.rect(sx, b - h, 4, h, 4)
        pyxel.line(sx, b - h, sx, b - 1, 2)
        pyxel.tri(sx, b - h, sx + 3, b - h, sx + 1.5, b - h - 3, 4)
    pyxel.line(x, b - 34, x + w - 1, b - 34, 2)


_DRAW = {
    "izba": _draw_izba,
    "longhouse": _draw_longhouse,
    "forge": _draw_forge,
    "well": _draw_well,
    "stall": _draw_stall,
    "banner": _draw_banner,
    "lantern": _draw_lantern,
    "fence": _draw_fence,
    "oak": _draw_oak,
    "barrels": _draw_barrels,
    "wall": _draw_wall,
}

_DEFAULT_W = {"izba": 8, "longhouse": 14, "forge": 7, "well": 3, "stall": 6, "fence": 4,
              "banner": 1, "lantern": 1, "oak": 2, "barrels": 2, "wall": 2}

KINDS = set(_DRAW)
