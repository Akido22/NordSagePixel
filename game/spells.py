"""Чары: руны, которые знает герой, и их действие.

Руна — предмет вида "rune": найденная или купленная, она сразу запоминается
(в суму не кладётся). Сила чар растёт с показателем «Дух».
"""

import math
import random
from dataclasses import dataclass

import pyxel

from . import audio, data, items
from .config import TILE
from .entities import rect_overlap


@dataclass(frozen=True)
class Spell:
    name: str
    cost: int  # мана
    cast: int  # кадров на сотворение (герой уязвим)
    color: int  # цвет свечения руки
    ground_only: bool = False
    damage: int = 0  # огонь: урон (+ Дух)
    speed: float = 0.0  # огонь: скорость полёта
    duration: int = 0  # щит: сколько кадров гасит удары
    heal: int = 0  # лечение (+ Дух)


KNOWN = ("rune_fire", "rune_shield", "rune_heal")  # чары, у которых есть действие в коде


def _load():
    result = {}
    for rune_id, sec in data.sections("spells.toml"):
        if rune_id not in KNOWN:
            raise data.DataError(f"{sec.where()}: для руны «{rune_id}» нет действия в коде; есть: {', '.join(KNOWN)}")
        items.check_ids([rune_id], sec.where())
        result[rune_id] = Spell(
            name=sec.get("name", str), cost=sec.get("cost", int), cast=sec.get("cast", int),
            color=sec.get("color", int), ground_only=sec.get("ground_only", bool, False),
            damage=sec.get("damage", int, 0), speed=sec.get("speed", float, 0.0),
            duration=sec.get("duration", int, 0), heal=sec.get("heal", int, 0))
        sec.check_unknown()
    return result


SPELLS = _load()


def fire_damage(spirit):
    return SPELLS["rune_fire"].damage + spirit


def heal_amount(spirit):
    return SPELLS["rune_heal"].heal + spirit


def release(spell_id, player, world):
    """Срабатывание чар в конце сотворения."""
    spirit = player.inv.stats["spi"]
    if spell_id == "rune_fire":
        x = player.cx + player.facing * 8
        speed = SPELLS["rune_fire"].speed
        world.projectiles.append(Fireball(x, player.y + 9, player.facing * speed, fire_damage(spirit)))
        audio.sfx(audio.FIRE)
    elif spell_id == "rune_shield":
        player.shield_t = SPELLS["rune_shield"].duration
        audio.sfx(audio.CHARGED)
        world.sparks(player.cx, player.cy, 10)
    elif spell_id == "rune_heal":
        healed = player.heal(heal_amount(spirit))
        world.float_text(player.cx, player.y - 4, f"+{healed}", 11)
        audio.sfx(audio.HEAL)
        for _ in range(14):
            world.particles.append([player.cx + random.uniform(-6, 6), player.y + random.uniform(0, 15),
                                    random.uniform(-0.2, 0.2), random.uniform(-1.0, -0.4),
                                    random.randint(20, 36), random.choice((11, 3, 15)), 0.0])


class Fireball:
    """Огненный шар Кеназ: летит прямо, взрывается о врага или стену."""

    w, h = 6, 6
    deflectable = False

    def __init__(self, x, y, vx, damage):
        self.x = x - self.w / 2
        self.y = y - self.h / 2
        self.vx = vx
        self.damage = damage
        self.dead = False
        self.life = 90

    def update(self, world):
        self.life -= 1
        self.x += self.vx
        if pyxel.frame_count % 2 == 0:
            world.particles.append([self.x + self.w / 2, self.y + self.h / 2, -self.vx * 0.2,
                                    random.uniform(-0.3, 0.3), random.randint(6, 12),
                                    random.choice((9, 10, 8)), 0.0])
        cx = self.x + self.w / 2
        if self.life <= 0 or world.level.is_solid(int(cx // TILE), int((self.y + self.h / 2) // TILE)):
            self._burst(world)
            return
        for e in world.enemies:
            if not e.dead and rect_overlap(self.x, self.y, self.w, self.h, e):
                e.take_hit(self.damage, 1 if self.vx > 0 else -1, world)
                self._burst(world)
                return

    def _burst(self, world):
        self.dead = True
        cx, cy = self.x + self.w / 2, self.y + self.h / 2
        for _ in range(10):
            world.particles.append([cx, cy, random.uniform(-1.4, 1.4), random.uniform(-1.6, 0.4),
                                    random.randint(8, 16), random.choice((9, 10, 8)), 0.03])

    def draw(self):
        cx, cy = self.x + self.w / 2, self.y + self.h / 2
        flick = pyxel.frame_count % 4 < 2
        pyxel.circ(cx, cy, 3, 8)
        pyxel.circ(cx, cy, 2, 9 if flick else 10)
        pyxel.pset(cx, cy, 15)


def draw_shield_aura(player):
    """Золотое сияние щита Перуна вокруг героя; к концу мерцает."""
    t = player.shield_t
    if t <= 0 or (t < 40 and (t // 3) % 2):
        return
    cx, cy = player.cx, player.cy
    pyxel.dither(0.25)
    pyxel.circ(cx, cy, 16, 10)
    pyxel.dither(1.0)
    pyxel.circb(cx, cy, 16, 10)
    a0 = pyxel.frame_count * 0.08
    for i in range(4):
        a = a0 + i * math.pi / 2
        pyxel.pset(cx + math.cos(a) * 16, cy + math.sin(a) * 16, 15)
