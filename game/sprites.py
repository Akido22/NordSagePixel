"""Спрайт-листы из assets/sprites: загрузка и рисование гуманоидов по слоям, оружия и волка.

Гуманоид собирается из слоёв, лежащих на одинаковой сетке кадров:
ноги -> туловище (рубаха/доспех/платье) -> голова -> шлем. «Облик» (look) —
список (лист, перекраска); перекраска меняет цвета палитры, так из одних
листов получаются герой, драугры, ярл и жители.

Кадры и точки привязки (кисть, спина, голова, угол оружия) описаны в
humanoid.json. Листы создаёт tools/make_sprites.py; их можно править вручную.
"""

import json
import math
import os

import pyxel

from .config import ROOT_DIR

SPRITES_DIR = os.path.join(ROOT_DIR, "assets", "sprites")

_sheets = {}
HUM = {}  # описание кадров гуманоида
WOLF = {}
WEAPONS = {}
FW = FH = 0

ARMOR_SHEETS = {"shirt": "hero_torso_shirt", "leather": "hero_torso_leather", "mail": "hero_torso_mail"}
HELMET_SHEETS = {"cap": "hero_helmet_cap", "shishak": "hero_helmet_shishak"}


def _json(name):
    with open(os.path.join(SPRITES_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def init():
    global FW, FH
    HUM.update(_json("humanoid.json"))
    WOLF.update(_json("wolf.json"))
    WEAPONS.update(_json("weapons.json"))
    FW, FH = HUM["frame_w"], HUM["frame_h"]
    for fn in os.listdir(SPRITES_DIR):
        if fn.endswith(".png"):
            _sheets[fn[:-4]] = pyxel.Image.from_image(os.path.join(SPRITES_DIR, fn))


# ------------------------------------------------------------ кадры
def anim(name, i=0):
    """Кадр анимации по счётчику (зацикленно)."""
    frames = HUM["anims"][name]
    return frames[int(i) % len(frames)]


def anim_at(name, progress, start=0):
    """Кадр анимации по доле 0..1 (без зацикливания); start — с какого кадра."""
    frames = HUM["anims"][name][start:]
    return frames[min(len(frames) - 1, max(0, int(progress * len(frames))))]


def info(frame):
    return HUM["frames"][frame]


def anchor(frame, key, cx, bottom, facing, scale=1):
    """Точка привязки кадра (hand/back/head) в мировых координатах."""
    fx, fy = HUM["frames"][frame][key]
    return cx + (fx - FW / 2) * facing * scale, bottom + (fy - FH) * scale


# ------------------------------------------------------------ рисование
def _tint(tint):
    if tint:
        for src, dst in tint.items():
            pyxel.pal(int(src, 16), int(dst, 16))


def draw_look(look, frame, cx, bottom, facing, scale=1, flash=False, extra=None):
    """Рисует облик (слои) кадром frame; (cx, bottom) — середина низа кадра."""
    cols = HUM["cols"]
    u = (frame % cols) * FW
    v = (frame // cols) * FH
    x = cx - FW / 2
    y = bottom - FH * scale / 2 - FH / 2
    w = FW if facing > 0 else -FW
    for sheet, tint in look:
        pyxel.pal()
        _tint(tint)
        _tint(extra)
        if flash:
            for c in range(1, 16):
                pyxel.pal(c, 15)
        pyxel.blt(x, y, _sheets[sheet], u, v, w, FH, 0, scale=scale)
    pyxel.pal()


def draw_weapon(item, angle, hx, hy, facing, scale=1, tint=None):
    """Оружие с хватом в точке (hx, hy); angle — 0: клинок вверх, по часовой."""
    order = WEAPONS["order"]
    kind = item.icon if item.icon in order else "sword"
    idx = order.index(kind)
    cw, ch = WEAPONS["cell"]
    gx, gy = WEAPONS["grip"]
    ox, oy = gx - cw / 2, gy - ch / 2  # хват относительно центра ячейки
    a = math.radians(angle * facing)
    rx = ox * math.cos(a) - oy * math.sin(a)
    ry = ox * math.sin(a) + oy * math.cos(a)
    cx, cy = hx - rx * scale, hy - ry * scale
    pyxel.pal()
    _tint(getattr(item, "tint", None))
    _tint(tint)
    pyxel.blt(cx - cw / 2, cy - ch / 2, _sheets["weapons"], idx * cw, 0, cw * facing, ch, 0,
              rotate=angle * facing, scale=scale)
    pyxel.pal()


def weapon_tip(angle, hx, hy, facing, length=14):
    a = math.radians(angle)
    return hx + math.sin(a) * length * facing, hy - math.cos(a) * length


def draw_wolf(anim_name, i, cx, bottom, facing, flash=False, extra=None):
    frames = WOLF["anims"][anim_name]
    n = frames[int(i) % len(frames)]
    w, h = WOLF["frame_w"], WOLF["frame_h"]
    _tint(extra)
    if flash:
        for c in range(1, 16):
            pyxel.pal(c, 15)
    pyxel.blt(cx - w / 2, bottom - h, _sheets["wolf"], n * w, 0, w if facing > 0 else -w, h, 0)
    pyxel.pal()


# ------------------------------------------------------------ облики
def hero_look(inventory):
    armor = inventory.equipped("armor")
    helmet = inventory.equipped("helmet")
    look = [("hero_legs", None),
            (ARMOR_SHEETS.get(armor.id if armor else "", "hero_torso_plain"), None),
            ("hero_head_male", None)]
    if helmet and helmet.id in HELMET_SHEETS:
        look.append((HELMET_SHEETS[helmet.id], None))
    return look


DRAUGR_HEAD = {"e": "6", "a": "7", "c": "f"}  # бледная кожа, седые космы, светящиеся глаза
DRAUGR_LOOK = [
    ("hero_legs", {"5": "1", "7": "5", "2": "1"}),
    ("hero_torso_mail", {"6": "5", "5": "1", "f": "6", "2": "1", "a": "2"}),
    ("hero_head_male", DRAUGR_HEAD),
    ("hero_helmet_shishak", {"6": "5", "f": "6", "a": "2"}),
]
ARCHER_LOOK = [
    ("hero_legs", {"5": "1", "7": "5", "2": "1"}),
    ("hero_torso_leather", {"4": "3", "2": "1"}),
    ("hero_head_male", DRAUGR_HEAD),
    ("hero_helmet_cap", {"4": "3", "7": "3"}),  # капюшон
]
JARL_LOOK = [
    ("hero_legs", {"5": "1", "7": "2", "2": "1"}),
    ("hero_torso_mail", {"6": "d", "5": "1", "f": "6", "2": "1"}),
    ("hero_head_male", {"e": "6", "a": "7"}),
    ("hero_helmet_crown", None),
]
