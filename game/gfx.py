"""Пиксельная графика: описание спрайтов строками и их загрузка в банки Pyxel.

Символы в спрайтах: '.' — прозрачный (цвет 0), 0-9/a-f — индекс цвета палитры.
"""

import math

import pyxel

SPRITE_BANK = 0
HERO_BANK = 1

# ---------------------------------------------------------------- тайлы 8x8
TILE_GRASS = 0
TILE_DIRT = 1
TILE_STONE = 2
TILE_PLANK = 3
TILE_SPIKES = 4
TILE_LOG = 5
TILE_TUFT = 6
TILE_MUSHROOM = 7
TILE_BOARDWALK = 8
TILE_FLAGSTONE = 9

_TILES = [
    # трава поверх земли
    ["b..b.b..", "bbbbbbbb", "3bb3bbb3", "23322332", "22222422", "24222222", "22222242", "22422222"],
    # земля
    ["22222222", "22422222", "22222242", "22222222", "24222222", "22222422", "22222222", "22242222"],
    # камень
    ["66666665", "65555551", "65555551", "65555151", "65551551", "65555551", "65555551", "51111111"],
    # доска (проходимая снизу платформа)
    ["44444444", "46444644", "22222222", ".2....2.", "........", "........", "........", "........"],
    # колья
    ["........", "..6...6.", "..6...6.", ".666.666", ".464.464", ".444.444", "24442444", "22222222"],
    # бревенчатый сруб
    ["24444442", "44444444", "44444444", "22222222", "24444442", "44444444", "44444444", "22222222"],
    # пучок травы (декор)
    ["........", "........", "........", "........", "........", "b..b....", ".b.b.b..", ".bbbb3b."],
    # мухомор (декор)
    ["........", "........", "..888...", ".87888..", ".88878..", "...7....", "...7....", "..777..."],
    # деревянная мостовая
    ["44444444", "42444424", "22222222", "21222212", "22242222", "22222222", "24222242", "22222222"],
    # каменные плиты площади
    ["76667666", "65556555", "65556555", "51115111", "22222222", "22422222", "22222242", "22222222"],
]

# ---------------------------------------------------------------- иконки 8x8
ICON_Y = 16
_ICONS = {
    "knife": ["........", "......6.", ".....f6.", "....f6..", "...a6...", "..22....", ".22.....", "........"],
    "sword": ["......f6", ".....f6.", "....f6..", ".a.f6...", "..a6....", "..2a....", ".2......", "a......."],
    "axe": ["....66..", "...6f66.", "..6f6.4.", "..66.4..", "....4...", "...4....", "..4.....", ".2......"],
    "spear": ["......66", "...a.6f6", "....466.", "...4.a..", "..4.....", ".4......", "4.......", "........"],
    "shield": ["..2222..", ".244442.", "24444442", "24466442", "24466442", "24444442", ".244442.", "..2222.."],
    "cap": ["........", "...44...", "..4444..", ".444444.", ".444444.", "77777777", "........", "........"],
    "helmet": ["...aa...", "...66...", "..6ff6..", ".66f666.", ".666666.", "6a6aa6a6", "6..66..6", "...66..."],
    "shirt": [".77..77.", "77788877", "77778777", ".777777.", ".777777.", ".878787.", ".777777.", "........"],
    "hammer": ["..a..a..", "...aa...", "...aa...", "...aa...", "aaaaaaaa", "a6aaaa6a", ".aaaaaa.", "..a..a.."],
    "lunnitsa": ["...66...", "..6..6..", "..6666..", ".6ffff6.", "66....66", "6......6", "6......6", "........"],
    "honey": ["..7777..", ".777777.", "..2222..", ".99a999.", "999a9999", "99999999", ".999999.", "..9999.."],
    "bread": ["........", "........", "..9999..", ".9a99a9.", "99999999", "94999949", ".444444.", "........"],
    "coin": ["........", "..6666..", ".6ffff6.", ".6f56f6.", ".6f65f6.", ".6ffff6.", "..6666..", "........"],
    "heart": ["........", ".88.88..", "8f88888.", "8888888.", ".88888..", "..888...", "...8....", "........"],
    "empty_heart": ["........", ".11.11..", "1551551.", "1555551.", ".15551..", "..151...", "...1....", "........"],
}
ICON_INDEX = {name: i for i, name in enumerate(_ICONS)}

# ---------------------------------------------------------------- крупные спрайты
OBJ_Y = 32
_RUNESTONE = [
    "................",
    ".....111111.....",
    "....15555551....",
    "...1566655551...",
    "...1565c55551...",
    "...156c5c5551...",
    "...1565c55551...",
    "...155c5c5551...",
    "...1555c55551...",
    "...15c5c5c551...",
    "...155c5c5551...",
    "...1555c55551...",
    "...1555555551...",
    "..115555555511..",
    "..1b3b11111b31..",
    ".1bbbb3333bbbb1.",
]
_CHEST_CLOSED = [
    "................",
    "..111111111111..",
    ".14444444444441.",
    ".16444444444461.",
    ".14444444444441.",
    ".111111aa111111.",
    ".14444a11a44441.",
    ".16444a11a44461.",
    ".144444aa444441.",
    ".16444444444461.",
    ".14444444444441.",
    ".11111111111111.",
]
_CHEST_OPEN = [
    "................",
    ".11111111111111.",
    ".14444444444441.",
    ".11111111111111.",
    ".12a2222a22a221.",
    ".14444411444441.",
    ".16444411444461.",
    ".14444444444441.",
    ".16444444444461.",
    ".14444444444441.",
    ".14444444444441.",
    ".11111111111111.",
]
_WOLF_A = [
    "...........1.1..",
    "..........151511",
    ".11.......15a551",
    "1561111111555661",
    ".155565555555661",
    "..15555555555611",
    "..156666666661..",
    "...151....151...",
    "...151....151...",
    "...11.....11....",
]
_WOLF_B = _WOLF_A[:7] + [
    "..151......151..",
    ".151........151.",
    ".11..........11.",
]

SPR_RUNESTONE = (0, OBJ_Y, 16, 16)
SPR_CHEST_CLOSED = (16, OBJ_Y, 16, 12)
SPR_CHEST_OPEN = (32, OBJ_Y, 16, 12)
SPR_WOLF = [(48, OBJ_Y, 16, 10), (64, OBJ_Y, 16, 10)]

# ---------------------------------------------------------------- гуманоиды
# Кадр 16x20: шлем с 2-й строки, голова с 4-й, туловище с 11-й, ноги с 16-й.
FRAME_W = 16
FRAME_H = 20

_HEAD = ["..1111..", ".1aaaa1.", "1aaaaee1", "1aaaece1", "1aaeeee1", ".1aaaaa1", "..1aaa1."]
_TORSO = {
    "idle": ["18888a81", "88888a88", "e8888a8e", "12222a21", "18888881"],
    "attack": ["18888a81...", "88888a8888e", "18888a81...", "12222a21...", "18888881..."],
    "block": ["18888a81..", "88888a888e", "18888a81..", "12222a21..", "18888881.."],
}
_LEGS = {
    "stand": [".155551.", ".15..51.", ".17..71.", ".22..22."],
    "run0": [".155551.", "155..551", "17....71", "22....22"],
    "run1": [".155551.", "..1551..", "..1771..", "..2222.."],
    "run2": [".155551.", ".1551...", ".17.71..", ".22.22.."],
    "jump": ["1555551.", "17...551", "22....71", "......22"],
    "fall": [".155551.", ".15..51.", "17....71", "2......2"],
}
_HELMET = ["...11...", "..1661..", ".166661.", "16666661", "1a6a6a61", "......6."]

# (сдвиг головы, туловище, ноги)
_FRAMES = [
    (0, "idle", "stand"),   # 0 стойка
    (1, "idle", "stand"),   # 1 стойка (дыхание)
    (0, "idle", "run0"),    # 2 бег
    (1, "idle", "run1"),    # 3
    (0, "idle", "run2"),    # 4
    (1, "idle", "run1"),    # 5
    (0, "idle", "jump"),    # 6 прыжок
    (0, "idle", "fall"),    # 7 падение
    (0, "attack", "stand"),  # 8 удар
    (0, "attack", "jump"),  # 9 удар в воздухе
    (0, "block", "stand"),  # 10 блок щитом
]
F_IDLE = (0, 1)
F_RUN = (2, 3, 4, 5)
F_JUMP = 6
F_FALL = 7
F_ATTACK = 8
F_ATTACK_AIR = 9
F_BLOCK = 10

# Положение кисти (точка хвата оружия) в кадре.
HAND_IDLE = (11, 13)
HAND_ATTACK = (14, 12)
HAND_BLOCK = (13, 12)

HERO_ROW = 0
DRAUGR_ROW = FRAME_H
NPC_ROW0 = FRAME_H * 2  # жители: по строке на каждого, кадры 0-1 (стойка)

_HEAD_FEMALE = ["..1111..", ".188881.", "1aaaaee1", "1aaaece1", "1aaeeee1", "1a1eee1.", "1a.111.."]
_LEGS_SKIRT = [".188881.", "18888881", "18888881", ".122221."]

DRAUGR_TINT = {"a": "5", "e": "b", "c": "f", "8": "2", "2": "1", "5": "2", "7": "5"}
DRAUGR_HELMET_TINT = {"6": "5", "a": "2"}


def _pad(rows, w):
    return [r.ljust(w, ".") for r in rows]


def _to_hex(rows):
    return ["".join("0" if c == "." else c for c in r) for r in rows]


def _stamp(canvas, part, x, y, tint=None):
    for j, row in enumerate(part):
        cy = y + j
        if not 0 <= cy < len(canvas):
            continue
        for i, c in enumerate(row):
            cx = x + i
            if c == "." or not 0 <= cx < len(canvas[0]):
                continue
            if tint:
                c = tint.get(c, c)
            canvas[cy][cx] = c


def build_humanoid(row_y, base_tint=None, armor_tint=None, helmet_tint=None, helmet=False):
    """Собирает лист кадров персонажа в банк HERO_BANK на строке row_y.

    base_tint — замена цветов всего тела, armor_tint — только туловища
    (так отображается надетый доспех), helmet — рисовать ли шлем.
    """
    img = pyxel.images[HERO_BANK]
    for n, (dy, torso_key, legs_key) in enumerate(_FRAMES):
        canvas = [["."] * FRAME_W for _ in range(FRAME_H)]
        torso_tint = dict(base_tint or {})
        if armor_tint:
            torso_tint.update(armor_tint)
        _stamp(canvas, _LEGS[legs_key], 4, 16, base_tint)
        _stamp(canvas, _TORSO[torso_key], 4, 11, torso_tint)
        _stamp(canvas, _HEAD, 4, 4 + dy, base_tint)
        if helmet:
            _stamp(canvas, _HELMET, 4, 2 + dy, helmet_tint)
        img.set(n * FRAME_W, row_y, _to_hex(["".join(r) for r in canvas]))


def build_npc(index, base_tint=None, body_tint=None, female=False, helmet=False, helmet_tint=None):
    """Собирает два кадра стойки жителя в строку NPC_ROW0 + index * FRAME_H. Возвращает строку."""
    row_y = NPC_ROW0 + index * FRAME_H
    img = pyxel.images[HERO_BANK]
    torso_tint = dict(base_tint or {})
    torso_tint.update(body_tint or {})
    for n, dy in enumerate((0, 1)):
        canvas = [["."] * FRAME_W for _ in range(FRAME_H)]
        if female:
            _stamp(canvas, _LEGS_SKIRT, 4, 16, torso_tint)
        else:
            _stamp(canvas, _LEGS["stand"], 4, 16, base_tint)
        _stamp(canvas, _TORSO["idle"], 4, 11, torso_tint)
        _stamp(canvas, _HEAD_FEMALE if female else _HEAD, 4, 4 + dy, base_tint)
        if helmet:
            _stamp(canvas, _HELMET, 4, 2 + dy, helmet_tint)
        img.set(n * FRAME_W, row_y, _to_hex(["".join(r) for r in canvas]))
    return row_y


def init():
    img = pyxel.images[SPRITE_BANK]
    for i, t in enumerate(_TILES):
        img.set(i * 8, 0, _to_hex(t))
    for i, rows in enumerate(_ICONS.values()):
        img.set(i * 8, ICON_Y, _to_hex(rows))
    img.set(SPR_RUNESTONE[0], SPR_RUNESTONE[1], _to_hex(_pad(_RUNESTONE, 16)))
    img.set(SPR_CHEST_CLOSED[0], SPR_CHEST_CLOSED[1], _to_hex(_pad(_CHEST_CLOSED, 16)))
    img.set(SPR_CHEST_OPEN[0], SPR_CHEST_OPEN[1], _to_hex(_pad(_CHEST_OPEN, 16)))
    img.set(SPR_WOLF[0][0], SPR_WOLF[0][1], _to_hex(_pad(_WOLF_A, 16)))
    img.set(SPR_WOLF[1][0], SPR_WOLF[1][1], _to_hex(_pad(_WOLF_B, 16)))
    build_humanoid(DRAUGR_ROW, base_tint=DRAUGR_TINT, helmet_tint=DRAUGR_HELMET_TINT, helmet=True)


# ---------------------------------------------------------------- рисование
def apply_tint(tint):
    if tint:
        for src, dst in tint.items():
            pyxel.pal(int(src, 16), int(dst, 16))


def tile(tile_id, x, y):
    pyxel.blt(x, y, SPRITE_BANK, tile_id * 8, 0, 8, 8, 0)


def sprite(spr, x, y, flip=False):
    u, v, w, h = spr
    pyxel.blt(x, y, SPRITE_BANK, u, v, -w if flip else w, h, 0)


def icon(name, x, y, tint=None, scale=1):
    """Рисует иконку 8x8; при scale>1 левый верхний угол остаётся в (x, y)."""
    idx = ICON_INDEX[name]
    apply_tint(tint)
    off = (8 * scale - 8) / 2
    pyxel.blt(x + off, y + off, SPRITE_BANK, idx * 8, ICON_Y, 8, 8, 0, scale=scale)
    pyxel.pal()


def humanoid(row_y, frame, x, y, flip=False, scale=1, rotate=0):
    off_x = (FRAME_W * scale - FRAME_W) / 2
    off_y = (FRAME_H * scale - FRAME_H) / 2
    w = -FRAME_W if flip else FRAME_W
    pyxel.blt(x + off_x, y + off_y, HERO_BANK, frame * FRAME_W, row_y, w, FRAME_H, 0,
              rotate=rotate, scale=scale)


def weapon(item, gx, gy, facing, angle, scale=1):
    """Рисует оружие с хватом в точке (gx, gy).

    angle — поворот относительно положения иконки (клинок вверх-вправо),
    положительный — по часовой стрелке. facing: 1 вправо, -1 влево.
    """
    idx = ICON_INDEX[item.icon]
    rad = math.radians(angle)
    # Вектор от хвата к центру иконки (хват в левом нижнем углу).
    vx, vy = 2.5 * scale, -2.5 * scale
    rx = vx * math.cos(rad) - vy * math.sin(rad)
    ry = vx * math.sin(rad) + vy * math.cos(rad)
    cx = gx + rx * facing
    cy = gy + ry
    apply_tint(item.tint)
    pyxel.blt(cx - 4, cy - 4, SPRITE_BANK, idx * 8, ICON_Y, 8 * facing, 8, 0,
              rotate=angle * facing, scale=scale)
    pyxel.pal()


def shield(item, cx, cy, scale=1):
    rim, body, boss = item.shield_colors
    r = 3 * scale
    pyxel.circ(cx, cy, r, body)
    pyxel.circb(cx, cy, r, rim)
    if scale > 1:
        pyxel.circ(cx, cy, scale - 1, boss)
    else:
        pyxel.pset(cx, cy, boss)
