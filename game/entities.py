"""Игровые сущности: герой, враги, предметы и объекты уровня."""

import math

import pyxel

from . import gfx, items, ui
from .config import TILE
from .npcs import NPC_INDEX, NPCS

GRAVITY = 0.22
MAX_FALL = 4.5


def overlap(a, b):
    return a.x < b.x + b.w and b.x < a.x + a.w and a.y < b.y + b.h and b.y < a.y + a.h


def rect_overlap(ax, ay, aw, ah, b):
    return ax < b.x + b.w and b.x < ax + aw and ay < b.y + b.h and b.y < ay + ah


class Body:
    """Прямоугольник с физикой и столкновениями с тайлами."""

    w = 8
    h = 8

    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.hit_wall = False
        self.on_platform = False

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2

    def apply_gravity(self):
        self.vy = min(self.vy + GRAVITY, MAX_FALL)

    def move(self, level, drop_through=False):
        self.hit_wall = False
        # --- по горизонтали
        self.x += self.vx
        top = int(self.y // TILE)
        bottom = int((self.y + self.h - 0.01) // TILE)
        if self.vx > 0:
            edge = int((self.x + self.w - 0.01) // TILE)
            if any(level.is_solid(edge, ty) for ty in range(top, bottom + 1)):
                self.x = edge * TILE - self.w
                self.vx = 0
                self.hit_wall = True
        elif self.vx < 0:
            edge = int(self.x // TILE)
            if any(level.is_solid(edge, ty) for ty in range(top, bottom + 1)):
                self.x = (edge + 1) * TILE
                self.vx = 0
                self.hit_wall = True
        # --- по вертикали
        prev_bottom = self.y + self.h
        self.y += self.vy
        self.on_ground = False
        self.on_platform = False
        left = int(self.x // TILE)
        right = int((self.x + self.w - 0.01) // TILE)
        if self.vy > 0:
            edge = int((self.y + self.h - 0.01) // TILE)
            for tx in range(left, right + 1):
                solid = level.is_solid(tx, edge)
                plank = (not drop_through and level.is_platform(tx, edge)
                         and prev_bottom <= edge * TILE + 0.5)
                if solid or plank:
                    self.y = edge * TILE - self.h
                    self.vy = 0
                    self.on_ground = True
                    self.on_platform = plank and not solid
                    break
        elif self.vy < 0:
            edge = int(self.y // TILE)
            if any(level.is_solid(tx, edge) for tx in range(left, right + 1)):
                self.y = (edge + 1) * TILE
                self.vy = 0

    def ground_ahead(self, level, direction):
        """Есть ли опора впереди (чтобы враги не падали с обрывов)."""
        fx = self.x + self.w + 1 if direction > 0 else self.x - 1
        tx = int(fx // TILE)
        ty = int((self.y + self.h + 1) // TILE)
        return level.is_solid(tx, ty) or level.is_platform(tx, ty)


# ===================================================================== отрисовка гуманоидов
def draw_humanoid(row, frame, x, y, facing, weapon=None, shield=None, weapon_angle=None,
                  flash=False, scale=1, shield_front=False):
    """Рисует гуманоида со щитом и оружием. (x, y) — левый верхний угол хитбокса 8x15.

    weapon_angle — угол оружия в руке для удара (None — оружие опущено в стойке).
    shield_front — щит поднят перед собой (блок), иначе висит за спиной.
    """
    sx = x - 4 * scale
    sy = y - 5 * scale

    def fx(px):
        return px if facing > 0 else gfx.FRAME_W - 1 - px

    if flash:
        for c in range(1, 16):
            pyxel.pal(c, 15)
    if shield and not shield_front:
        gfx.shield(shield, sx + (fx(5) + 0.5) * scale, sy + 13 * scale, scale)
    gfx.humanoid(row, frame, sx, sy, flip=facing < 0, scale=scale)
    if weapon and not shield_front:
        if weapon_angle is not None:
            hand, angle = gfx.HAND_ATTACK, weapon_angle
        else:
            hand, angle = gfx.HAND_IDLE, -10
        gfx.weapon(weapon, sx + (fx(hand[0]) + 0.5) * scale, sy + (hand[1] + 0.5) * scale, facing, angle, scale)
    if shield_front:
        hand = gfx.HAND_BLOCK
        cx = sx + (fx(hand[0]) + 0.5) * scale
        cy = sy + (hand[1] + 0.5) * scale
        if shield:
            gfx.shield(shield, cx, cy, scale * 1.4)
        elif weapon:
            gfx.weapon(weapon, cx, cy + 2, facing, -60, scale)  # блок оружием
    if flash:
        pyxel.pal()


def draw_stun_stars(cx, y):
    """Кружащиеся звёздочки над головой оглушённого."""
    t = pyxel.frame_count
    for i in range(3):
        a = t * 0.15 + i * 2.1
        pyxel.pset(cx + math.cos(a) * 5, y + math.sin(a) * 1.5, 10 if i % 2 else 15)


# ===================================================================== предметы на земле
class Pickup(Body):
    w = 8
    h = 8

    def __init__(self, x, y, kind, uid=None, floating=False):
        super().__init__(x, y)
        self.kind = kind  # "coin" или id предмета
        self.uid = uid  # для предметов с карты (чтобы помнить, что подобраны)
        self.floating = floating
        self.age = 0
        self.taken = False

    def update(self, world):
        self.age += 1
        if not self.floating:
            self.apply_gravity()
            self.vx *= 0.95
            self.move(world.level)
        p = world.player
        if not p.dead and self.age > 20 and overlap(self, p):
            world.collect(self)

    def draw(self):
        bob = math.sin(self.age * 0.08) * 1.5 if self.floating else 0
        if self.kind == "coin":
            # «Вращение» монеты сужением спрайта.
            phase = (self.age // 6) % 4
            w = [8, 6, 2, 6][phase]
            pyxel.blt(self.x + (8 - w) / 2, self.y + bob, gfx.SPRITE_BANK,
                      gfx.ICON_INDEX["coin"] * 8 + (8 - w) // 2, gfx.ICON_Y, w, 8, 0)
        else:
            item = items.get(self.kind)
            gfx.icon(item.icon, self.x, self.y + bob, item.tint)
            if (self.age // 10) % 6 == 0:
                pyxel.pset(self.x + 6, self.y + bob + 1, 15)


# ===================================================================== объекты уровня
class Chest:
    w, h = 16, 12

    def __init__(self, tx, ty, loot):
        self.uid = f"{tx},{ty}"
        self.x = tx * TILE - 4
        self.y = (ty + 1) * TILE - self.h
        self.loot = list(loot)
        self.opened = False

    def draw(self):
        gfx.sprite(gfx.SPR_CHEST_OPEN if self.opened else gfx.SPR_CHEST_CLOSED, self.x, self.y)

    def hint(self):
        return None if self.opened else "открыть"


class Runestone:
    w, h = 16, 16

    def __init__(self, tx, ty):
        self.uid = f"{tx},{ty}"
        self.x = tx * TILE - 4
        self.y = (ty + 1) * TILE - self.h
        self.active = False

    def draw(self):
        t = pyxel.frame_count
        if self.active:
            glow = 10 if (t // 12) % 3 else 9
            pyxel.pal(12, glow)
            pyxel.dither(0.25 + 0.1 * math.sin(t * 0.08))
            pyxel.circ(self.x + 8, self.y + 8, 11, 10)
            pyxel.dither(1.0)
        gfx.sprite(gfx.SPR_RUNESTONE, self.x, self.y)
        pyxel.pal()

    def hint(self):
        return "сохранить"


class Sign:
    w, h = 10, 12

    def __init__(self, tx, ty, text):
        self.x = tx * TILE - 1
        self.y = (ty + 1) * TILE - self.h
        self.text = text

    def draw(self):
        x, y = self.x, self.y
        pyxel.rect(x + 4, y + 4, 2, 8, 2)
        pyxel.rect(x, y, 10, 6, 4)
        pyxel.rectb(x, y, 10, 6, 2)
        pyxel.line(x + 2, y + 2, x + 7, y + 2, 2)
        pyxel.line(x + 2, y + 4, x + 5, y + 4, 2)

    def hint(self):
        return None


class Gate:
    """Врата-выход. target — имя локации или "end" (конец пробного пути)."""

    def __init__(self, tx, ty, target="end", spawn=None, style="forest"):
        self.style = style
        self.locked = False
        self.w, self.h = (40, 56) if style == "town" else (24, 32)
        self.x = tx * TILE + 4 - self.w // 2
        self.y = (ty + 1) * TILE - self.h
        self.target = target
        self.spawn = spawn

    def draw(self):
        if self.style == "town":
            self._draw_town()
        elif self.style == "barrow":
            self._draw_barrow()
        else:
            self._draw_forest()

    def _draw_barrow(self):
        """Каменный проход: столбы и перекрытие с рунами; заперт — завален плитой."""
        x, y = self.x, self.y
        t = pyxel.frame_count
        if self.locked:
            pyxel.rect(x + 4, y + 8, 16, 24, 5)
            pyxel.line(x + 4, y + 18, x + 19, y + 21, 1)
            pyxel.line(x + 9, y + 8, x + 11, y + 31, 1)
        else:
            pyxel.rect(x + 4, y + 8, 16, 24, 0)
            pyxel.dither(0.5 + 0.2 * math.sin(t * 0.05))
            pyxel.rect(x + 6, y + 10, 12, 22, 12)
            pyxel.dither(1.0)
        pyxel.rect(x, y + 6, 4, 26, 5)
        pyxel.rect(x + 20, y + 6, 4, 26, 5)
        pyxel.rect(x - 2, y, 28, 7, 6)
        pyxel.line(x - 2, y + 6, x + 25, y + 6, 1)
        rune = 10 if not self.locked else 1
        for i in range(4):
            pyxel.line(x + 3 + i * 6, y + 2, x + 3 + i * 6, y + 5, rune)
            pyxel.pset(x + 4 + i * 6, y + 3, rune)

    def _draw_forest(self):
        x, y = self.x, self.y
        t = pyxel.frame_count
        # Проём со светом.
        pyxel.dither(0.6 + 0.2 * math.sin(t * 0.05))
        pyxel.rect(x + 5, y + 10, 14, 22, 10)
        pyxel.dither(1.0)
        # Столбы и перекладина.
        pyxel.rect(x + 2, y + 8, 3, 24, 4)
        pyxel.rect(x + 19, y + 8, 3, 24, 4)
        pyxel.rect(x, y + 7, 24, 3, 2)
        # Двускатная крыша с «коньком».
        pyxel.tri(x - 2, y + 7, x + 12, y - 2, x + 26, y + 7, 2)
        pyxel.tri(x + 1, y + 6, x + 12, y, x + 23, y + 6, 4)
        pyxel.line(x + 12, y - 2, x + 12, y - 6, 2)
        pyxel.line(x + 12, y - 6, x + 15, y - 5, 2)
        pyxel.pset(x + 14, y - 6, 2)
        # Резьба-ромбы.
        for i in range(3):
            pyxel.pset(x + 3, y + 13 + i * 6, 10)
            pyxel.pset(x + 20, y + 13 + i * 6, 10)
        pyxel.rect(x + 8, y + 8, 8, 1, 8)

    def _draw_town(self):
        """Проездная башня городища: две срубные вежи с шатрами и ворота между ними."""
        x, b = self.x, self.y + self.h
        t = pyxel.frame_count
        # Проём: за ним виден лес.
        pyxel.rect(x + 10, b - 30, 20, 30, 1)
        pyxel.tri(x + 12, b - 4, x + 17, b - 20, x + 22, b - 4, 3)
        pyxel.tri(x + 20, b - 2, x + 25, b - 24, x + 30, b - 2, 3)
        pyxel.rect(x + 10, b - 3, 20, 3, 2)
        # Распахнутые створки.
        pyxel.rect(x + 10, b - 28, 4, 28, 4)
        pyxel.rect(x + 26, b - 28, 4, 28, 4)
        for yy in range(b - 25, b, 6):
            pyxel.line(x + 10, yy, x + 13, yy, 2)
            pyxel.line(x + 26, yy, x + 29, yy, 2)
        # Надвратная клеть.
        pyxel.rect(x + 8, b - 42, 24, 12, 4)
        for yy in range(b - 39, b - 30, 4):
            pyxel.line(x + 8, yy, x + 31, yy, 2)
        pyxel.rect(x + 17, b - 39, 6, 5, 1)
        ui.rhombus(x + 20, b - 33, 2, 10)
        # Вежи.
        for tx in (x, x + 30):
            pyxel.rect(tx, b - 48, 10, 48, 4)
            for yy in range(b - 45, b, 4):
                pyxel.line(tx, yy, tx + 9, yy, 2)
            pyxel.rect(tx + 3, b - 40, 4, 5, 1)  # бойница
            pyxel.rect(tx - 2, b - 50, 14, 3, 2)
            pyxel.tri(tx - 2, b - 50, tx + 5, b - 66, tx + 12, b - 50, 2)
            pyxel.tri(tx + 1, b - 51, tx + 5, b - 62, tx + 9, b - 51, 4)
            pyxel.line(tx + 5, b - 66, tx + 5, b - 70, 2)
        # Флажок на правой веже.
        sway = int(math.sin(t * 0.08) * 1.5)
        pyxel.tri(x + 35, b - 70, x + 35, b - 66, x + 41 + sway, b - 68, 8)
        # Крыша над клетью.
        pyxel.tri(x + 6, b - 42, x + 20, b - 52, x + 34, b - 42, 2)
        pyxel.tri(x + 9, b - 43, x + 20, b - 50, x + 31, b - 43, 4)

    def hint(self):
        if self.locked:
            return "заперто"
        return "в путь" if self.target != "end" else "войти"


class EdgeExit:
    """Невидимый выход на краю карты: срабатывает, когда герой в него заходит."""

    w, h = 8, 24

    def __init__(self, tx, ty, target, spawn):
        self.x = tx * TILE
        self.y = (ty + 1) * TILE - self.h
        self.target = target
        self.spawn = spawn

    def draw(self):
        """Дорожный указатель со стрелкой в сторону выхода."""
        b = self.y + self.h
        left = self.x < TILE * 2
        px = self.x + (10 if left else -4)
        pyxel.rect(px, b - 18, 2, 18, 2)
        bx = px - 4
        pyxel.rect(bx, b - 18, 11, 6, 4)
        pyxel.rectb(bx, b - 18, 11, 6, 2)
        tip = bx + 2 if left else bx + 8
        d = 1 if left else -1
        pyxel.line(bx + 2, b - 15, bx + 8, b - 15, 7)
        pyxel.pset(tip + d, b - 16, 7)
        pyxel.pset(tip + d, b - 14, 7)


class Stela:
    """Стела Предков — место сохранения в городе."""

    w, h = 48, 96

    def __init__(self, tx, ty):
        self.uid = f"{tx},{ty}"
        self.cx = tx * TILE + 4
        self.base = (ty + 1) * TILE
        self.x = self.cx - self.w // 2
        self.y = self.base - self.h
        self.active = False

    def draw(self):
        cx, b = self.cx, self.base
        t = pyxel.frame_count
        pulse = math.sin(t * 0.06)
        if self.active:
            pyxel.dither(0.14 + 0.05 * pulse)
            pyxel.circ(cx, b - 50, 36, 10)
            pyxel.dither(1.0)
        # Ступени постамента.
        for i, (half, col) in enumerate(((24, 5), (18, 5), (12, 6))):
            y = b - 4 * (i + 1)
            pyxel.rect(cx - half, y, half * 2, 4, col)
            pyxel.line(cx - half, y, cx + half - 1, y, 6 if col == 5 else 15)
            pyxel.line(cx - half, y + 3, cx + half - 1, y + 3, 1)
        # Камень стелы: сужается кверху, макушка заострена.
        bot, top = b - 12, b - 78
        pyxel.tri(cx - 9, bot, cx + 9, bot, cx - 6, top, 5)
        pyxel.tri(cx + 9, bot, cx + 6, top, cx - 6, top, 5)
        pyxel.tri(cx - 6, top, cx + 6, top, cx, top - 10, 5)
        pyxel.line(cx - 9, bot, cx - 6, top, 6)
        pyxel.line(cx - 8, bot, cx - 5, top, 6)
        pyxel.line(cx - 6, top, cx, top - 10, 6)
        pyxel.line(cx + 9, bot, cx + 6, top, 1)
        pyxel.line(cx + 6, top, cx, top - 10, 1)
        # Пояс-обвязка у основания и у макушки.
        pyxel.rect(cx - 9, bot - 6, 18, 2, 6)
        pyxel.rect(cx - 6, top + 9, 12, 1, 6)
        # Резьба: солнце, цепь ромбов и руны. После поклона резьба светится.
        carve = (10 if pulse > -0.3 else 9) if self.active else 1
        pyxel.circb(cx, top + 2, 3, carve)
        pyxel.pset(cx, top + 2, carve)
        for a in range(8):
            ang = a * math.pi / 4
            pyxel.pset(cx + math.cos(ang) * 5, top + 2 + math.sin(ang) * 5, carve)
        for y in range(top + 15, bot - 9, 6):
            ui.rhombus(cx, y, 2, carve)
            pyxel.pset(cx, y, 5)
        for i, y in enumerate(range(top + 15, bot - 12, 7)):
            side = -5 if i % 2 else 5
            pyxel.line(cx + side, y, cx + side, y + 4, carve)
            pyxel.pset(cx + side + (1 if side < 0 else -1), y + 1 + i % 3, carve)
        # Венки и свечи на постаменте.
        for fx in range(cx - 22, cx + 23, 3):
            pyxel.pset(fx, b - 5, 11)
            if (fx // 3) % 3 == 0:
                pyxel.pset(fx, b - 6, 8 if (fx // 9) % 2 else 10)
        for sx in (cx - 15, cx + 14):
            pyxel.rect(sx, b - 11, 2, 3, 7)
            pyxel.pset(sx + (t // 7) % 2, b - 12, 10 if (t // 5) % 3 else 9)

    def hint(self):
        return "поклониться"


class Npc:
    w, h = 8, 15

    def __init__(self, tx, ty, npc_id):
        self.id = npc_id
        self.data = NPCS[npc_id]
        self.row = gfx.build_npc(NPC_INDEX[npc_id], self.data.base_tint, self.data.body_tint,
                                 self.data.female, self.data.helmet, self.data.helmet_tint)
        self.x = tx * TILE
        self.y = (ty + 1) * TILE - self.h
        self.facing = self.data.facing
        self.line = -1  # -1: молчит
        self.phase = tx % 40

    @property
    def talking(self):
        return self.line >= 0

    def talk(self):
        """Следующая реплика; после последней разговор заканчивается."""
        self.line += 1
        if self.line >= len(self.data.lines):
            self.line = -1

    def update(self, world):
        p = world.player
        if abs(p.cx - (self.x + 4)) < 40:
            self.facing = 1 if p.cx > self.x + 4 else -1
        else:
            self.facing = self.data.facing
            self.line = -1

    def draw(self):
        frame = ((pyxel.frame_count + self.phase) // 36) % 2
        draw_humanoid(self.row, frame, self.x, self.y, self.facing, weapon=self.data.held)

    def hint(self):
        return None if self.talking else "говорить"


class Decor:
    """Неинтерактивные украшения: берёза, идол, костёр."""

    def __init__(self, kind, tx, ty):
        self.kind = kind
        self.x = tx * TILE
        self.base = (ty + 1) * TILE

    def draw(self):
        x, b = self.x, self.base
        if self.kind == "B":
            pyxel.rect(x + 3, b - 38, 3, 38, 15)
            for i, yy in enumerate(range(b - 34, b - 2, 6)):
                pyxel.line(x + 3 + (i % 2), yy, x + 4 + (i % 2), yy, 1)
            pyxel.line(x + 5, b - 26, x + 9, b - 30, 15)
            for cx, cy, r, col in ((x + 4, b - 42, 9, 3), (x - 2, b - 36, 6, 3), (x + 10, b - 34, 6, 3),
                                   (x + 4, b - 44, 7, 11), (x - 1, b - 37, 4, 11), (x + 9, b - 36, 4, 11)):
                pyxel.circ(cx, cy, r, col)
        elif self.kind == "I":
            # Деревянный идол с резным ликом.
            pyxel.rect(x + 1, b - 26, 6, 26, 4)
            pyxel.rect(x + 1, b - 26, 6, 1, 2)
            pyxel.elli(x, b - 31, 8, 6, 2)
            pyxel.pset(x + 2, b - 21, 1)
            pyxel.pset(x + 5, b - 21, 1)
            pyxel.line(x + 3, b - 20, x + 3, b - 17, 2)
            pyxel.line(x + 2, b - 15, x + 5, b - 15, 2)
            pyxel.rect(x + 1, b - 11, 6, 1, 8)
            pyxel.pset(x + 2, b - 8, 10)
            pyxel.pset(x + 5, b - 8, 10)
        elif self.kind == "F":
            t = pyxel.frame_count
            pyxel.dither(0.1 + 0.03 * math.sin(t * 0.2))
            pyxel.circ(x + 4, b - 5, 10, 9)
            pyxel.dither(1.0)
            pyxel.line(x, b - 1, x + 8, b - 3, 2)
            pyxel.line(x, b - 3, x + 8, b - 1, 4)
            for i in range(7):
                ph = (t // 3 + i * 5) % 12
                fx = x + 1 + (i * 3 + (t // 5) % 3) % 7
                fy = b - 3 - ph
                col = 10 if ph < 4 else 9 if ph < 8 else 8
                pyxel.pset(fx, fy, col)
            pyxel.rect(x + 2, b - 5, 5, 2, 9)
            pyxel.pset(x + 4, b - 6, 10)
