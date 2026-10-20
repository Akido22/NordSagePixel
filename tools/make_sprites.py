"""Генератор стартовой графики «Северной Саги».

Рисует спрайт-листы гуманоидов (по слоям), волка и оружия «скелетом»: для
каждого кадра задаётся поза (углы конечностей), а слои одежды рисуются по одним
и тем же суставам — поэтому шлем, доспех и тело всегда совпадают.

Результат: assets/sprites/*.png, описание кадров *.json и палитра palette.gpl
для Aseprite. Готовые PNG можно править вручную — генератор не перезаписывает
существующие файлы без флага --force.

Запуск:  python tools/make_sprites.py [--force]
"""

import json
import math
import os
import sys
from dataclasses import dataclass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pyxel  # noqa: E402

from game.config import PALETTE  # noqa: E402

OUT = os.path.join(ROOT, "assets", "sprites")
FW, FH = 24, 32  # кадр гуманоида
COLS = 8
OUTLINE = 1
SKIN = 14


# ============================================================ геометрия
def vdir(angle):
    """Единичный вектор: 0° — вниз, 90° — вперёд (вправо), 180° — вверх."""
    r = math.radians(angle)
    return math.sin(r), math.cos(r)


def add(p, v, k=1.0):
    return p[0] + v[0] * k, p[1] + v[1] * k


def rotate_about(p, pivot, deg):
    r = math.radians(deg)
    x, y = p[0] - pivot[0], p[1] - pivot[1]
    return pivot[0] + x * math.cos(r) - y * math.sin(r), pivot[1] + x * math.sin(r) + y * math.cos(r)


@dataclass
class Pose:
    dx: float = 0
    dy: float = 0
    lean: float = 0  # наклон корпуса вперёд, градусы
    tilt: float = 0  # наклон головы
    back_leg: tuple = (-6, 2)  # (угол бедра, сгиб колена)
    front_leg: tuple = (6, -2)
    back_arm: tuple = (-10, 10)  # (угол плеча, сгиб локтя)
    front_arm: tuple = (20, 60)
    weapon: float = None  # угол оружия (0 — клинок вверх), None — оружие не рисуется
    spin: float = 0  # поворот всей фигуры (перекат, падение)
    pivot: tuple = (12, 22)
    shift: tuple = (0, 0)  # сдвиг после поворота


def joints(p):
    hip = (12 + p.dx, 22 + p.dy)
    up = vdir(180 - p.lean)
    neck = add(hip, up, 7)
    head = add(neck, vdir(180 - p.lean - p.tilt), 4)
    j = {"hip": hip, "neck": neck, "head": head, "up": up}
    j["sh_f"] = add(neck, (0.5, 1))
    j["sh_b"] = add(neck, (-0.5, 1))
    for side, (a, k) in (("b", p.back_leg), ("f", p.front_leg)):
        h = add(hip, (0.5 if side == "f" else -0.5, 0))
        knee = add(h, vdir(a), 4.5)
        foot = add(knee, vdir(a + k), 4.5)
        j["hip_" + side], j["knee_" + side], j["foot_" + side] = h, knee, foot
        j["shin_" + side] = a + k
    for side, (s, e) in (("b", p.back_arm), ("f", p.front_arm)):
        sh = j["sh_" + side]
        elbow = add(sh, vdir(s), 4)
        hand = add(elbow, vdir(s + e), 3.5)
        j["elbow_" + side], j["hand_" + side] = elbow, hand
    if p.spin:
        for key, v in list(j.items()):
            if isinstance(v, tuple):
                j[key] = rotate_about(v, p.pivot, p.spin)
        j["up"] = vdir(180 - p.lean + p.spin)
        for side in "bf":
            j["shin_" + side] += p.spin
    if p.shift != (0, 0):
        for key, v in list(j.items()):
            if isinstance(v, tuple) and key != "up":
                j[key] = add(v, p.shift)
    j["spin"] = p.spin
    return j


# ============================================================ кисти
class Canvas:
    def __init__(self, img, ox, oy):
        self.img, self.ox, self.oy = img, ox, oy

    def _p(self, p):
        return self.ox + p[0], self.oy + p[1]

    def seg(self, a, b, t, col):
        """Толстый отрезок толщиной t пикселей."""
        ax, ay = self._p(a)
        bx, by = self._p(b)
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy) or 1
        nx, ny = -dy / length, dx / length
        steps = max(1, int(t * 2))
        for i in range(steps + 1):
            o = -(t - 1) / 2 + (t - 1) * i / steps
            self.img.line(ax + nx * o, ay + ny * o, bx + nx * o, by + ny * o, col)
        if t > 2:
            r = (t - 1) / 2
            self.img.circ(ax, ay, r, col)
            self.img.circ(bx, by, r, col)

    def circ(self, c, r, col):
        x, y = self._p(c)
        self.img.circ(x, y, r, col)

    def square(self, c, size, col):
        x, y = self._p(c)
        h = size / 2
        self.img.rect(round(x - h), round(y - h), size, size, col)

    def pset(self, p, col):
        x, y = self._p(p)
        self.img.pset(round(x - 0.01), round(y - 0.01), col)

    def poly(self, pts, col):
        pts = [self._p(p) for p in pts]
        for i in range(1, len(pts) - 1):
            self.img.tri(*pts[0], *pts[i], *pts[i + 1], col)

    def poly_outlined(self, pts, col):
        for i in range(len(pts)):
            self.seg(pts[i], pts[(i + 1) % len(pts)], 3, OUTLINE)
        self.poly(pts, col)

    def limb(self, pts, t, col):
        """Конечность с контуром: сначала толще тёмным, потом цветом."""
        for a, b in zip(pts, pts[1:]):
            self.seg(a, b, t + 2, OUTLINE)
        for a, b in zip(pts, pts[1:]):
            self.seg(a, b, t, col)


def torso_quad(j, below=3.0, hip_w=3.5, neck_w=4.0):
    up = j["up"]
    perp = (-up[1], up[0])
    if perp[0] < 0:
        perp = (-perp[0], -perp[1])
    bottom = add(j["hip"], up, -below)
    return [add(bottom, perp, -hip_w), add(bottom, perp, hip_w),
            add(j["neck"], perp, neck_w), add(j["neck"], perp, -neck_w)], perp, bottom


# ============================================================ слои гуманоида
def draw_legs(c, j, pants=5, wraps=7, boots=2):
    for side in "bf":
        h, k, f = j["hip_" + side], j["knee_" + side], j["foot_" + side]
        c.limb([h, k], 3, pants)
        c.limb([k, f], 3, wraps)
        toe = vdir(j["shin_" + side] + 90)
        c.limb([add(f, vdir(j["shin_" + side]), -1.2), f, add(f, toe, 2)], 3, boots)
        if wraps == 7:  # обмотки онучей
            mid = add(k, vdir(j["shin_" + side]), 2.2)
            c.pset(mid, 5)


TORSO_STYLES = {
    # тело, рукав, отделка
    "plain": (7, 7, None),
    "shirt": (7, 7, 8),
    "leather": (4, 4, 2),
    "mail": (6, 6, 5),
    "dress": (8, 8, 10),
}


def _arm(c, j, side, sleeve, cuff=None):
    sh, el, hd = j["sh_" + side], j["elbow_" + side], j["hand_" + side]
    c.limb([sh, el, hd], 3, sleeve)
    if cuff is not None:
        c.seg(add(el, (hd[0] - el[0], hd[1] - el[1]), 0.45), add(el, (hd[0] - el[0], hd[1] - el[1]), 0.55), 3, cuff)
    c.square(hd, 4, OUTLINE)
    c.square(hd, 2, SKIN)


def draw_torso(c, j, style):
    body, sleeve, trim = TORSO_STYLES[style]
    _arm(c, j, "b", 5 if style == "mail" else sleeve, trim if style == "shirt" else None)
    below = 9.5 if style == "dress" else (4 if style == "mail" else 3)
    quad, perp, bottom = torso_quad(j, below=below)
    if style == "dress":
        quad[0] = add(bottom, perp, -6)
        quad[1] = add(bottom, perp, 6)
    c.poly_outlined(quad, body)
    c.circ(j["sh_f"], 2, body)
    up = j["up"]
    belt = add(j["hip"], up, 1)
    if style == "mail":
        for i in range(-3, 4):
            for k in range(-6, 4):
                if (i + k) % 2 == 0:
                    c.pset(add(add(j["hip"], perp, i), up, k), 5)
        c.seg(add(bottom, perp, -3), add(bottom, perp, 3), 1, 15)
    elif style == "leather":
        c.seg(j["sh_b"], add(belt, perp, 3), 1, 2)
        c.circ(j["sh_f"], 1.5, 2)
    elif style == "shirt":
        c.seg(add(bottom, perp, -3), add(bottom, perp, 3), 1, 8)
        c.seg(add(j["neck"], perp, -1.5), add(j["neck"], up, -2.5), 1, 8)
        c.seg(add(j["neck"], perp, 1.5), add(j["neck"], up, -2.5), 1, 8)
    elif style == "dress":
        c.seg(add(bottom, perp, -5.5), add(bottom, perp, 5.5), 1, 10)
        c.seg(add(j["neck"], perp, -2), add(j["neck"], perp, 2), 1, 10)
    if style != "dress":
        c.seg(add(belt, perp, -3.5), add(belt, perp, 3.5), 2, 2)
        c.pset(add(belt, perp, 1), 10)
    _arm(c, j, "f", sleeve, trim if style == "shirt" else None)


def draw_head(c, j, style="male"):
    h = j["head"]
    tilt = j["up"]
    fwd = (-tilt[1], tilt[0])
    if fwd[0] < 0 and j.get("spin", 0) == 0:
        fwd = (-fwd[0], -fwd[1])
    if style == "female":
        braid_end = add(add(h, fwd, -3.5), tilt, -8)
        c.limb([add(h, fwd, -3), braid_end], 2, 10)
    c.circ(h, 4.5, OUTLINE)
    if style == "male":
        c.circ(add(add(h, fwd, 1.8), tilt, -2.8), 2.4, OUTLINE)
    c.circ(h, 3.5, SKIN)  # лицо
    c.circ(add(add(h, fwd, -1.6), tilt, 1.4), 3.1, 10)  # волосы: шапкой сзади и сверху
    c.seg(add(add(h, fwd, -0.5), tilt, 3.3), add(add(h, fwd, 2.5), tilt, 2.6), 1, 10)  # чёлка
    if style == "male":
        c.circ(add(add(h, fwd, 1.8), tilt, -2.8), 1.4, 10)  # короткая борода
        c.seg(add(add(h, fwd, 1), tilt, -1.4), add(add(h, fwd, 3.2), tilt, -1.4), 1, 10)  # усы
    else:
        c.seg(add(add(h, fwd, -3), tilt, 2.2), add(add(h, fwd, 3), tilt, 2.2), 1, 8)  # очелье
    c.pset(add(add(h, fwd, 2), tilt, 0.8), 12)  # глаз


def draw_helmet(c, j, style):
    h = j["head"]
    up = j["up"]
    fwd = (-up[1], up[0])
    if fwd[0] < 0 and j.get("spin", 0) == 0:
        fwd = (-fwd[0], -fwd[1])
    if style == "cap":
        top = add(h, up, 3.2)
        c.circ(top, 4.2, OUTLINE)
        c.circ(top, 3.2, 4)
        c.seg(add(add(h, up, 2), fwd, -4.5), add(add(h, up, 2), fwd, 4.5), 4, OUTLINE)
        c.seg(add(add(h, up, 2), fwd, -4), add(add(h, up, 2), fwd, 4), 2, 7)
        return
    dome = 6 if style == "shishak" else 5
    base_l = add(add(h, up, 0.5), fwd, -4.5)
    base_r = add(add(h, up, 0.5), fwd, 4.5)
    apex = add(h, up, 9)
    c.poly_outlined([base_l, base_r, apex], dome)
    c.circ(add(h, up, 3), 3.4, dome)
    c.seg(add(add(h, up, 5), fwd, -1), add(add(h, up, 2), fwd, -3), 1, 15 if style == "shishak" else 6)
    c.seg(base_l, base_r, 2, 10)
    c.pset(add(apex, up, 1), 10)
    c.seg(add(base_r, fwd, -2), add(add(base_r, fwd, -2), up, -3), 1, dome)  # наносник
    if style == "crown":
        for k in (-3, 0, 3):
            p = add(add(h, up, 1.5), fwd, k)
            c.seg(p, add(p, up, 3), 1, 10)
        c.pset(add(add(h, up, 1), fwd, 0), 8)


# ============================================================ позы
def poses():
    """Все кадры гуманоида по порядку и таблица анимаций."""
    frames, anims = [], {}

    def anim(name, items):
        anims[name] = list(range(len(frames), len(frames) + len(items)))
        frames.extend(items)

    anim("idle", [Pose(dy=b, lean=2, back_leg=(-8, 4), front_leg=(8, -4), back_arm=(-10, 10),
                       front_arm=(20, 60 + b * 4), weapon=30) for b in (0, 0, 1, 1)])
    run = []
    for i in range(6):
        s = math.sin(i / 6 * 2 * math.pi)
        run.append(Pose(dy=-1 if i % 3 == 1 else 0, lean=8,
                        front_leg=(40 * s, -15 - 45 * max(0.0, -s)),
                        back_leg=(-40 * s, -15 - 45 * max(0.0, s)),
                        back_arm=(35 * s, 40), front_arm=(25 - 30 * s, 70), weapon=70))
    anim("run", run)
    anim("jump", [Pose(dy=-1, back_leg=(-15, -70), front_leg=(40, -80), back_arm=(-70, 30),
                       front_arm=(45, 70), weapon=20)])
    anim("fall", [Pose(back_leg=(-15, -20), front_leg=(20, -10), back_arm=(-120, 30),
                       front_arm=(70, 40), weapon=45)])
    anim("roll", [Pose(dy=3, lean=45, back_leg=(80, -150), front_leg=(95, -150), back_arm=(70, 80),
                       front_arm=(80, 80), spin=30 + i * 60, pivot=(12, 22), shift=(0, 4))
                  for i in range(6)])
    anim("block", [Pose(lean=-4, back_leg=(-25, 15), front_leg=(22, -18), back_arm=(-20, 30),
                        front_arm=(80, 10), weapon=20)])
    # Лёгкий удар сверху вниз и обратный взмах (вторая часть серии).
    lunge = dict(back_leg=(-30, 10), front_leg=(35, -30))
    anim("attack", [
        Pose(lean=-6, back_leg=(-15, 5), front_leg=(15, -10), back_arm=(-30, 30), front_arm=(170, 10), weapon=-60),
        Pose(lean=2, back_leg=(-20, 5), front_leg=(25, -20), back_arm=(-30, 30), front_arm=(130, 0), weapon=20),
        Pose(lean=10, back_arm=(-40, 20), front_arm=(80, 0), weapon=95, **lunge),
        Pose(lean=8, back_arm=(-30, 20), front_arm=(45, 10), weapon=140, **lunge),
    ])
    anim("attack2", [
        Pose(lean=4, back_arm=(-30, 20), front_arm=(40, 10), weapon=150, **lunge),
        Pose(lean=6, back_arm=(-30, 20), front_arm=(85, 0), weapon=100, **lunge),
        Pose(lean=0, back_leg=(-20, 5), front_leg=(25, -20), back_arm=(-30, 30), front_arm=(135, 0), weapon=30),
        Pose(lean=-4, back_leg=(-15, 5), front_leg=(15, -10), back_arm=(-30, 30), front_arm=(165, 0), weapon=-20),
    ])
    anim("heavy", [
        Pose(dy=2, lean=-12, back_leg=(-30, 40), front_leg=(25, -55), back_arm=(-40, 40), front_arm=(175, -10),
             weapon=-80),
        Pose(lean=0, back_leg=(-20, 10), front_leg=(25, -25), back_arm=(-30, 30), front_arm=(150, 0), weapon=-10),
        Pose(dy=1, lean=18, back_leg=(-35, 15), front_leg=(45, -45), back_arm=(-50, 20), front_arm=(70, 0),
             weapon=110),
        Pose(dy=1, lean=14, back_leg=(-35, 15), front_leg=(45, -45), back_arm=(-40, 20), front_arm=(35, 5),
             weapon=160),
    ])
    anim("plunge", [Pose(lean=10, back_leg=(10, -70), front_leg=(40, -80), back_arm=(-60, 20),
                         front_arm=(30, 0), weapon=180)])
    anim("cast", [Pose(lean=3, back_leg=(-10, 5), front_leg=(12, -8), back_arm=(-20, 30), front_arm=(85, 0)),
                  Pose(lean=5, back_leg=(-10, 5), front_leg=(12, -8), back_arm=(-25, 30), front_arm=(100, 0))])
    anim("hurt", [Pose(lean=-15, back_leg=(-20, 10), front_leg=(10, -20), back_arm=(-60, 30),
                       front_arm=(-30, 40), weapon=120)])
    anim("death", [
        Pose(lean=-20, back_leg=(-20, 10), front_leg=(10, -20), back_arm=(-60, 30), front_arm=(-30, 40)),
        Pose(dy=4, lean=25, back_leg=(30, -120), front_leg=(80, -90), back_arm=(10, 10), front_arm=(15, 10)),
        Pose(dy=4, lean=30, back_leg=(30, -120), front_leg=(80, -90), back_arm=(30, 10), front_arm=(40, 10),
             spin=40, pivot=(12, 26), shift=(0, 2)),
        Pose(lean=0, back_leg=(-4, 0), front_leg=(4, 0), back_arm=(10, 0), front_arm=(20, 0),
             spin=90, pivot=(12, 22), shift=(-2, 6)),
    ])
    return frames, anims


# ============================================================ волк
def wolf_frames():
    frames, anims = [], {}

    def anim(name, items):
        anims[name] = list(range(len(frames), len(frames) + len(items)))
        frames.extend(items)

    anim("run", [(math.sin(i / 4 * 2 * math.pi), 0) for i in range(4)])
    anim("idle", [(0.0, 0)])
    anim("crouch", [(0.0, 2)])
    anim("leap", [(1.2, -1)])
    return frames, anims


def draw_wolf(c, phase, low):
    body_c = (11, 8 + low)
    head = (18.5, 6 + low * 1.5)
    # хвост и задние лапы — позади
    c.limb([(5, 7 + low), (2, 5 + low), (1, 3 + low)], 2, 5)
    legs = [((8, 10 + low), phase), ((15, 10 + low), -phase)]
    for (x, y), ph in legs:
        c.limb([(x - 1, y), (x - 1 - ph * 1.8, 15)], 2, 5)
    c.circ(body_c, 5.5, OUTLINE)
    c.img.elli(c.ox + 3, c.oy + 4 + low, 17, 9, OUTLINE)
    c.img.elli(c.ox + 4, c.oy + 5 + low, 15, 7, 5)
    c.img.elli(c.ox + 6, c.oy + 8 + low, 11, 4, 6)  # светлое брюхо
    for (x, y), ph in legs:
        c.limb([(x + 1, y), (x + 1 + ph * 1.8, 15)], 2, 6)
    c.circ(head, 3.8, OUTLINE)
    c.circ(head, 2.8, 5)
    c.limb([add(head, (1, 1)), add(head, (5, 2))], 2, 6)  # морда
    c.pset(add(head, (5.5, 1.5)), OUTLINE)
    c.limb([add(head, (-1, -2)), add(head, (-0.5, -5))], 1, 5)  # ухо
    c.pset(add(head, (1, -1)), 10)  # глаз


# ============================================================ оружие
WEAPON_CELL = (16, 24)
WEAPON_GRIP = (8, 20)
WEAPONS = ["knife", "sword", "axe", "spear", "hammer"]


def draw_weapon(c, kind):
    g = WEAPON_GRIP
    if kind == "sword":
        c.limb([(8, 18), (8, 3)], 2, 6)
        c.seg((7.5, 4), (7.5, 16), 1, 15)
        c.pset((8, 2), 6)
        c.limb([(4, 17), (12, 17)], 1, 10)
        c.limb([(8, 18), (8, 21)], 1, 2)
        c.pset((8, 22), 10)
    elif kind == "knife":
        c.limb([(8, 17), (8, 10)], 2, 6)
        c.seg((7.5, 11), (7.5, 16), 1, 15)
        c.limb([(6, 17), (10, 17)], 1, 10)
        c.limb([(8, 18), (8, 21)], 1, 2)
    elif kind == "axe":
        c.limb([(8, 22), (8, 4)], 1, 4)
        c.poly_outlined([(9, 4), (14, 2), (14, 11), (9, 8)], 6)
        c.seg((14, 3), (14, 10), 1, 15)
        c.pset(g, 2)
    elif kind == "spear":
        c.limb([(8, 23), (8, 7)], 1, 4)
        c.poly_outlined([(8, 0), (10, 4), (8, 8), (6, 4)], 6)
        c.pset((8, 3), 15)
        c.limb([(5, 9), (11, 9)], 1, 10)
    elif kind == "hammer":
        c.limb([(8, 22), (8, 6)], 1, 4)
        c.poly_outlined([(4, 2), (12, 2), (12, 7), (4, 7)], 6)
        c.seg((5, 3), (11, 3), 1, 15)


# ============================================================ сохранение
def save_sheet(name, img, force):
    path = os.path.join(OUT, name + ".png")
    if os.path.exists(path) and not force:
        print("  пропущен (уже есть):", name)
        return
    img.save(path, 1)
    print("  записан:", name)


def main():
    force = "--force" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    pyxel.init(64, 64, title="make_sprites")
    pyxel.colors[:] = PALETTE

    frames, anims = poses()
    rows = (len(frames) + COLS - 1) // COLS
    sheet_w, sheet_h = COLS * FW, rows * FH
    joint_list = [joints(p) for p in frames]

    layers = {
        "legs": lambda c, j: draw_legs(c, j),
        "torso_plain": lambda c, j: draw_torso(c, j, "plain"),
        "torso_shirt": lambda c, j: draw_torso(c, j, "shirt"),
        "torso_leather": lambda c, j: draw_torso(c, j, "leather"),
        "torso_mail": lambda c, j: draw_torso(c, j, "mail"),
        "torso_dress": lambda c, j: draw_torso(c, j, "dress"),
        "head_male": lambda c, j: draw_head(c, j, "male"),
        "head_female": lambda c, j: draw_head(c, j, "female"),
        "helmet_cap": lambda c, j: draw_helmet(c, j, "cap"),
        "helmet_shishak": lambda c, j: draw_helmet(c, j, "shishak"),
        "helmet_crown": lambda c, j: draw_helmet(c, j, "crown"),
    }
    for name, fn in layers.items():
        img = pyxel.Image(sheet_w, sheet_h)
        img.cls(0)
        for n, j in enumerate(joint_list):
            c = Canvas(img, (n % COLS) * FW, (n // COLS) * FH)
            img.clip((n % COLS) * FW, (n // COLS) * FH, FW, FH)
            fn(c, j)
            img.clip()
        save_sheet("hero_" + name, img, force)

    meta = {"frame_w": FW, "frame_h": FH, "cols": COLS, "anims": anims, "frames": []}
    for p, j in zip(frames, joint_list):
        back = add(j["sh_b"], (j["hip"][0] - j["sh_b"][0], j["hip"][1] - j["sh_b"][1]), 0.35)
        meta["frames"].append({
            "hand": [round(j["hand_f"][0], 1), round(j["hand_f"][1], 1)],
            "back": [round(back[0] - 1.5, 1), round(back[1], 1)],
            "head": [round(j["head"][0], 1), round(j["head"][1], 1)],
            "weapon": p.weapon,
        })
    with open(os.path.join(OUT, "humanoid.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)

    # Волк.
    wframes, wanims = wolf_frames()
    img = pyxel.Image(len(wframes) * 24, 16)
    img.cls(0)
    for n, (phase, low) in enumerate(wframes):
        img.clip(n * 24, 0, 24, 16)
        draw_wolf(Canvas(img, n * 24, 0), phase, low)
        img.clip()
    save_sheet("wolf", img, force)
    with open(os.path.join(OUT, "wolf.json"), "w", encoding="utf-8") as f:
        json.dump({"frame_w": 24, "frame_h": 16, "anims": wanims}, f, ensure_ascii=False, indent=1)

    # Оружие в руке.
    cw, ch = WEAPON_CELL
    img = pyxel.Image(cw * len(WEAPONS), ch)
    img.cls(0)
    for n, kind in enumerate(WEAPONS):
        img.clip(n * cw, 0, cw, ch)
        draw_weapon(Canvas(img, n * cw, 0), kind)
        img.clip()
    save_sheet("weapons", img, force)
    with open(os.path.join(OUT, "weapons.json"), "w", encoding="utf-8") as f:
        json.dump({"cell": list(WEAPON_CELL), "grip": list(WEAPON_GRIP), "order": WEAPONS}, f, indent=1)

    # Палитра для Aseprite (GIMP .gpl): рисуйте только этими цветами, цвет 0 — прозрачный.
    with open(os.path.join(OUT, "palette.gpl"), "w", encoding="utf-8") as f:
        f.write("GIMP Palette\nName: Северная Сага\nColumns: 8\n#\n")
        for i, c in enumerate(PALETTE):
            f.write(f"{c >> 16:3d} {(c >> 8) & 255:3d} {c & 255:3d}\tcolor{i}\n")
    print("готово:", OUT)


if __name__ == "__main__":
    main()
