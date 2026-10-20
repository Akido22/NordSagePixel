"""Враги: волк, драугр, драугр со щитом, драугр-лучник, стрелы и тренировочное чучело.

Общее правило боя: каждая атака врага заметно «предупреждает» о себе (присед, замах,
натянутая тетива), её можно заблокировать щитом, а поднятым в нужный момент щитом —
парировать. Парированный враг оглушён, и следующий удар по нему критический.
"""

import math
from types import SimpleNamespace

import pyxel

from . import audio, data, sprites
from .config import TILE
from .entities import Body, draw_humanoid, draw_stun_stars, overlap, rect_overlap


def _sign(v):
    return 1 if v >= 0 else -1


class Enemy(Body):
    max_hp = 3
    contact_dmg = 1
    knock = 2.0
    silver = (1, 2)
    xp = 3
    ore_chance = 0.0  # шанс выронить железную крицу
    bread_chance = 0.0  # шанс выронить каравай
    stun_time = 80

    def __init__(self, x, y):
        super().__init__(x, y)
        self.hp = self.max_hp
        self.facing = -1
        self.dead = False
        self.hurt_t = 0
        self.flash = 0
        self.anim_t = 0
        self.stun_t = 0
        self.contact_cd = 0

    # ------------------------------------------------------------ получение урона
    def guards(self, direction, heavy, plunge):
        """Отражает ли враг этот удар (щитом)."""
        return False

    def on_guard(self, world, direction):
        pass

    def interrupt(self):
        """Сбить начатую атаку (при попадании или оглушении)."""

    def take_hit(self, dmg, direction, world, heavy=False, plunge=False):
        """direction — куда смотрит бьющий герой. Возвращает "hit" или "blocked"."""
        crit = self.stun_t > 0
        if crit:
            dmg = math.ceil(dmg * 2.5)
            self.stun_t = 0
        elif self.guards(direction, heavy, plunge):
            self.on_guard(world, direction)
            return "blocked"
        self.hp -= dmg
        self.hurt_t = 14
        self.flash = 6
        self.vx = direction * self.knock * (1.7 if heavy else 1.0)
        self.vy = -2.2 if heavy else -1.6
        self.facing = -direction
        self.interrupt()
        if crit:
            world.float_text(self.cx, self.y - 12, "КРИТ!", 10)
        world.float_text(self.cx, self.y - 4, str(dmg), 15 if crit else 10)
        world.sparks(self.cx - direction * 3, self.cy, 12 if crit or heavy else 6)
        world.freeze(7 if crit else 5 if heavy else 3)
        if crit or heavy:
            world.shake(3)
        if self.hp <= 0:
            self.dead = True
            audio.sfx(audio.KILL)
            world.on_enemy_killed(self)
        else:
            audio.sfx(audio.HEAVY if crit or heavy else audio.HIT)
        return "hit"

    def on_parried(self, world, player):
        self.stun_t = self.stun_time
        self.interrupt()
        self.vx = _sign(self.cx - player.cx) * 0.7  # недалеко: ответный удар должен доставать
        self.vy = -1.0

    def on_blocked(self, world, player):
        self.vx = _sign(self.cx - player.cx) * 1.8
        self.vy = -1.0
        self.hurt_t = 10
        self.interrupt()

    # ------------------------------------------------------------ цикл
    def update(self, world):
        self.anim_t += 1
        if self.flash > 0:
            self.flash -= 1
        if self.contact_cd > 0:
            self.contact_cd -= 1
        if self.stun_t > 0:
            self.stun_t -= 1
            self.vx *= 0.85
        elif self.hurt_t > 0:
            self.hurt_t -= 1
            self.vx *= 0.88
        else:
            self.think(world)
        self.apply_gravity()
        self.move(world.level)
        p = world.player
        if (self.contact_dmg and not p.dead and self.hurt_t == 0 and self.stun_t == 0
                and self.contact_cd == 0 and overlap(self, p)):
            result = p.take_damage(self.current_contact_dmg(), self.cx, world, source=self)
            if result != "miss":
                self.contact_cd = 30

    def current_contact_dmg(self):
        return self.contact_dmg

    def think(self, world):
        pass

    def player_near(self, world, dist_x, dist_y=28):
        p = world.player
        return not p.dead and abs(p.cx - self.cx) < dist_x and abs(p.cy - self.cy) < dist_y

    def patrol(self, world, speed):
        if self.hit_wall or (self.on_ground and not self.ground_ahead(world.level, self.facing)):
            self.facing = -self.facing
        self.vx = self.facing * speed

    def draw_status(self):
        if self.stun_t > 0:
            draw_stun_stars(self.cx, self.y - 6)


# ===================================================================== волк
class Wolf(Enemy):
    w = 18
    h = 11
    max_hp = 4
    contact_dmg = 1
    lunge_dmg = 3
    knock = 2.4
    silver = (1, 3)
    xp = 5
    CROUCH = 20
    LUNGE_CD = 90
    LUNGE_RANGE = 44
    CHASE_SPEED = 1.25
    PATROL_SPEED = 0.5
    SIGHT = 110

    def __init__(self, x, y):
        super().__init__(x, y)
        self.lunge_cd = 0
        self.crouch_t = 0
        self.lunging = False
        self.lunge_t = 0

    def interrupt(self):
        self.crouch_t = 0
        self.lunging = False

    def current_contact_dmg(self):
        return self.lunge_dmg if self.lunging else self.contact_dmg

    def think(self, world):
        if self.lunge_cd > 0:
            self.lunge_cd -= 1
        if self.lunging:
            self.lunge_t += 1
            if self.lunge_t > 4 and self.on_ground:
                self.lunging = False
                self.vx *= 0.3
            return
        if self.crouch_t > 0:  # присед перед прыжком — подсказка игроку
            self.crouch_t -= 1
            self.vx = 0
            if self.crouch_t == 0:
                self.vx = self.facing * 2.6
                self.vy = -2.4
                self.lunging = True
                self.lunge_t = 0
                self.lunge_cd = self.LUNGE_CD
            return
        if not self.on_ground:
            return
        p = world.player
        if self.player_near(world, self.SIGHT):
            self.facing = _sign(p.cx - self.cx)
            if not self.ground_ahead(world.level, self.facing):
                self.vx = 0
            elif abs(p.cx - self.cx) < self.LUNGE_RANGE and self.lunge_cd == 0:
                self.crouch_t = self.CROUCH
                self.vx = 0
            else:
                self.vx = self.facing * self.CHASE_SPEED
        else:
            self.patrol(world, self.PATROL_SPEED)

    def draw(self):
        eyes = {"a": "8"} if self.crouch_t and (self.crouch_t // 3) % 2 else None  # глаза вспыхивают
        if self.crouch_t:
            name, i = "crouch", 0
        elif not self.on_ground:
            name, i = "leap", 0
        elif abs(self.vx) > 0.1:
            name, i = "run", self.anim_t // 6
        else:
            name, i = "idle", 0
        sprites.draw_wolf(name, i, self.cx, self.y + self.h + 1, self.facing, self.flash > 0, eyes)
        self.draw_status()


# ===================================================================== драугры
RUSTY_SWORD = SimpleNamespace(icon="sword", tint={"f": "6", "6": "5", "a": "2"})
RUSTY_SHIELD = SimpleNamespace(shield_colors=(1, 5, 6))


class Draugr(Enemy):
    w = 10
    h = 22
    max_hp = 8
    contact_dmg = 1
    strike_dmg = 4
    knock = 1.3
    silver = (3, 5)
    xp = 10
    ore_chance = 0.35
    stun_time = 90
    REACH = 18
    WINDUP = 34
    RECOVER = 40
    CHASE_SPEED = 0.55
    PATROL_SPEED = 0.3
    SIGHT = 120

    def __init__(self, x, y):
        super().__init__(x, y)
        self.state = "walk"
        self.state_t = 0
        self.struck = False

    def _set(self, state, t):
        self.state = state
        self.state_t = t

    def interrupt(self):
        if self.state in ("windup", "strike"):
            self._set("recover", 24)

    def think(self, world):
        p = world.player
        if self.state == "walk":
            if self.player_near(world, self.SIGHT, 24):
                self.facing = _sign(p.cx - self.cx)
                if abs(p.cx - self.cx) < 20:
                    self._set("windup", self.WINDUP)
                    self.vx = 0
                elif self.ground_ahead(world.level, self.facing):
                    self.vx = self.facing * self.CHASE_SPEED
                else:
                    self.vx = 0
            else:
                self.patrol(world, self.PATROL_SPEED)
            return
        self.vx = 0
        self.state_t -= 1
        if self.state == "strike" and not self.struck and not p.dead:
            hx = self.x + self.w if self.facing > 0 else self.x - self.REACH
            if rect_overlap(hx, self.y, self.REACH, self.h, p):
                if p.take_damage(self.strike_dmg, self.cx, world, source=self) != "miss":
                    self.struck = True
        if self.state_t <= 0:
            if self.state == "windup":
                self._set("strike", 12)
                self.struck = False
                audio.sfx(audio.SWING)
            elif self.state == "strike":
                self._set("recover", self.RECOVER)
            else:
                self._set("walk", 0)

    def pose(self):
        """Кадр для текущего состояния."""
        if self.stun_t > 0 or self.hurt_t > 0:
            return sprites.anim("hurt")
        if self.state == "strike":
            return sprites.anim("attack", 2)
        if self.state == "windup":
            return sprites.anim("attack", 0)
        if self.state == "recover":
            return sprites.anim("attack", 3)
        if abs(self.vx) > 0.05:
            return sprites.anim("run", self.anim_t // 7)
        return sprites.anim("idle", self.anim_t // 18)

    def draw(self, shield=None, shield_front=False, frame=None):
        frame = self.pose() if frame is None else frame
        eyes = {"c": "8"} if self.state == "windup" and (self.state_t // 4) % 2 else None  # вспышка глаз
        draw_humanoid(sprites.DRAUGR_LOOK, frame, self.cx, self.y + self.h, self.facing,
                      weapon=RUSTY_SWORD, shield=shield, shield_front=shield_front,
                      flash=self.flash > 0, extra=eyes)
        self.draw_status()


class ShieldDraugr(Draugr):
    """Держит щит перед собой: лёгкие удары спереди отскакивают.

    Пробивают его тяжёлый удар, удар сверху, удар в спину, парирование
    или серия лёгких ударов, которая ломает стойку.
    """

    max_hp = 10
    silver = (4, 6)
    xp = 14
    GUARD_MAX = 3
    GUARD_REGEN = 120

    def __init__(self, x, y):
        super().__init__(x, y)
        self.guard = self.GUARD_MAX
        self.guard_regen = 0

    def guarding(self):
        return self.state in ("walk", "recover") and self.stun_t == 0 and self.hurt_t == 0

    def guards(self, direction, heavy, plunge):
        return not (heavy or plunge) and self.guarding() and direction == -self.facing

    def on_guard(self, world, direction):
        self.guard -= 1
        self.vx = direction * 0.8
        world.sparks(self.cx - direction * 5, self.y + 6, 5)
        if self.guard <= 0:
            audio.sfx(audio.GUARD_BREAK)
            world.float_text(self.cx, self.y - 10, "ЩИТ ПРОБИТ", 8)
            self.stun_t = 70
            self.guard = self.GUARD_MAX

    def think(self, world):
        if self.guard < self.GUARD_MAX:
            self.guard_regen += 1
            if self.guard_regen >= self.GUARD_REGEN:
                self.guard += 1
                self.guard_regen = 0
        super().think(world)

    def draw(self):
        guarding = self.guarding()
        frame = sprites.anim("block") if guarding and abs(self.vx) < 0.05 else None
        super().draw(shield=RUSTY_SHIELD, shield_front=guarding, frame=frame)


class Archer(Enemy):
    """Драугр-лучник: держит дистанцию и стреляет, предупреждая натянутой тетивой."""

    w = 10
    h = 22
    max_hp = 4
    contact_dmg = 1
    knock = 2.2
    silver = (2, 4)
    xp = 8
    ore_chance = 0.25
    stun_time = 90
    AIM = 44
    SHOT_CD = 50
    ARROW_SPEED = 2.8
    KEEP_AWAY = 48
    SIGHT = 150

    def __init__(self, x, y):
        super().__init__(x, y)
        self.state = "walk"
        self.state_t = 0
        self.cooldown = 30

    def interrupt(self):
        if self.state == "aim":
            self.state = "walk"
            self.cooldown = 40

    def think(self, world):
        p = world.player
        if self.cooldown > 0:
            self.cooldown -= 1
        if self.state == "aim":
            self.vx = 0
            self.facing = _sign(p.cx - self.cx)
            self.state_t -= 1
            if self.state_t <= 0:
                world.projectiles.append(Arrow(self.cx + self.facing * 8, self.y + 9,
                                               self.facing * self.ARROW_SPEED))
                audio.sfx(audio.BOW)
                self.state = "walk"
                self.cooldown = self.SHOT_CD
            return
        if not self.player_near(world, self.SIGHT, 40):
            self.patrol(world, 0.3)
            return
        dist = abs(p.cx - self.cx)
        self.facing = _sign(p.cx - self.cx)
        if dist < self.KEEP_AWAY and self.ground_ahead(world.level, -self.facing):
            self.vx = -self.facing * 0.7  # пятится, не сводя глаз с героя
        elif dist > 130 and self.ground_ahead(world.level, self.facing):
            self.vx = self.facing * 0.5
        else:
            self.vx = 0
            if self.cooldown == 0:
                self.state = "aim"
                self.state_t = self.AIM

    def draw(self):
        aiming = self.state == "aim"
        if self.stun_t > 0 or self.hurt_t > 0:
            frame = sprites.anim("hurt")
        elif aiming:
            frame = sprites.anim("cast", 0)
        elif abs(self.vx) > 0.05:
            frame = sprites.anim("run", self.anim_t // 7)
        else:
            frame = sprites.anim("idle", self.anim_t // 18)
        bottom = self.y + self.h
        draw_humanoid(sprites.ARCHER_LOOK, frame, self.cx, bottom, self.facing, flash=self.flash > 0)
        # Лук в вытянутой руке.
        hx, hy = sprites.anchor(frame, "hand", self.cx, bottom, self.facing)
        f = self.facing
        pyxel.line(hx, hy - 6, hx + f * 2, hy - 3, 4)
        pyxel.line(hx + f * 2, hy - 3, hx + f * 2, hy + 3, 4)
        pyxel.line(hx + f * 2, hy + 3, hx, hy + 6, 4)
        pull = 3 if aiming else 0
        pyxel.line(hx, hy - 6, hx - f * pull, hy, 7)
        pyxel.line(hx - f * pull, hy, hx, hy + 6, 7)
        if aiming:
            pyxel.line(hx - f * pull, hy, hx + f * 5, hy, 4)
            if self.state_t < 14 and (self.state_t // 2) % 2:
                pyxel.pset(hx + f * 6, hy, 15)  # блеск наконечника: сейчас выстрелит
        self.draw_status()


class Arrow:
    w, h = 6, 2
    DAMAGE = 2
    REFLECTED_DAMAGE = 3

    def __init__(self, x, y, vx):
        self.x = x - self.w / 2
        self.y = y
        self.vx = vx
        self.hostile = True
        self.dead = False
        self.life = 200

    @property
    def deflectable(self):
        return self.hostile

    def deflect(self, world):
        """Отбита ударом или парированием — летит обратно и ранит врагов."""
        self.vx = -self.vx * 1.3
        self.hostile = False
        self.life = 200
        world.sparks(self.x + self.w / 2, self.y, 5)
        audio.sfx(audio.BLOCK)

    def on_parried(self, world, player):
        self.deflect(world)

    def on_blocked(self, world, player):
        self.dead = True

    def update(self, world):
        self.life -= 1
        self.x += self.vx
        tip = self.x + (self.w if self.vx > 0 else 0)
        if self.life <= 0 or world.level.is_solid(int(tip // TILE), int((self.y + 1) // TILE)):
            self.dead = True
            world.sparks(tip, self.y, 2)
            return
        if self.hostile:
            p = world.player
            if not p.dead and rect_overlap(self.x, self.y, self.w, self.h, p):
                result = p.take_damage(self.DAMAGE, p.cx - _sign(self.vx) * 10, world, source=self)
                if result == "hit":
                    self.dead = True
        else:
            for e in world.enemies:
                if not e.dead and rect_overlap(self.x, self.y, self.w, self.h, e):
                    e.take_hit(self.REFLECTED_DAMAGE, _sign(self.vx), world)
                    self.dead = True
                    break

    def draw(self):
        x, y = self.x, self.y
        pyxel.line(x, y, x + self.w - 1, y, 4)
        if self.vx > 0:
            pyxel.pset(x + self.w, y, 6)
            pyxel.pset(x, y - 1, 7)
            pyxel.pset(x, y + 1, 7)
        else:
            pyxel.pset(x - 1, y, 6)
            pyxel.pset(x + self.w - 1, y - 1, 7)
            pyxel.pset(x + self.w - 1, y + 1, 7)


# ===================================================================== чучело
class Dummy(Enemy):
    """Соломенное чучело для отработки ударов: не нападает и не погибает."""

    w = 12
    h = 24
    max_hp = 999
    contact_dmg = 0
    knock = 0

    def __init__(self, x, y):
        super().__init__(x, y)
        self.wobble = 0.0

    def take_hit(self, dmg, direction, world, heavy=False, plunge=False):
        self.flash = 5
        self.wobble = direction * (4.0 if heavy else 2.5)
        world.float_text(self.cx, self.y - 4, str(dmg), 10)
        world.sparks(self.cx - direction * 3, self.cy, 8 if heavy else 4)
        world.freeze(5 if heavy else 3)
        audio.sfx(audio.HEAVY if heavy else audio.HIT)
        return "hit"

    def update(self, world):
        self.anim_t += 1
        if self.flash > 0:
            self.flash -= 1
        self.wobble *= 0.9

    def draw(self):
        b = self.y + self.h
        cx = self.cx
        lean = self.wobble * math.cos(self.anim_t * 0.5)
        if self.flash:
            for c in range(1, 16):
                pyxel.pal(c, 15)
        pyxel.rect(cx - 1, b - 26, 2, 26, 2)  # кол
        top = cx + lean
        pyxel.line(top - 9, b - 18, top + 9, b - 18, 4)  # руки-перекладина
        pyxel.pset(top - 10, b - 19, 10)
        pyxel.pset(top + 10, b - 19, 10)
        pyxel.elli(top - 6, b - 19, 12, 13, 10)  # соломенное тулово
        pyxel.line(top - 5, b - 12, top + 5, b - 12, 4)  # опояска
        pyxel.circ(top, b - 23, 4, 7)  # мешок-голова
        pyxel.pset(top - 1, b - 24, 1)
        pyxel.pset(top + 2, b - 24, 1)
        pyxel.line(top - 1, b - 21, top + 2, b - 21, 8)
        pyxel.pal()


# ===================================================================== числа из data/enemies.toml
_COMMON = {
    "hp": ("max_hp", int), "contact_damage": ("contact_dmg", int), "knockback": ("knock", float),
    "xp": ("xp", int), "silver": ("silver", list), "ore_chance": ("ore_chance", float),
    "bread_chance": ("bread_chance", float), "stun_frames": ("stun_time", int), "sight": ("SIGHT", int),
}


def _load():
    secs = dict(data.sections("enemies.toml"))
    spec = {
        "wolf": (Wolf, {"lunge_damage": ("lunge_dmg", int), "crouch_frames": ("CROUCH", int),
                        "lunge_cooldown": ("LUNGE_CD", int), "lunge_range": ("LUNGE_RANGE", int),
                        "chase_speed": ("CHASE_SPEED", float), "patrol_speed": ("PATROL_SPEED", float)}),
        "draugr": (Draugr, {"strike_damage": ("strike_dmg", int), "reach": ("REACH", int),
                            "windup_frames": ("WINDUP", int), "recover_frames": ("RECOVER", int),
                            "chase_speed": ("CHASE_SPEED", float), "patrol_speed": ("PATROL_SPEED", float)}),
        "shield_draugr": (ShieldDraugr, {"guard": ("GUARD_MAX", int), "guard_regen_frames": ("GUARD_REGEN", int)}),
        "archer": (Archer, {"aim_frames": ("AIM", int), "shot_cooldown": ("SHOT_CD", int),
                            "arrow_speed": ("ARROW_SPEED", float), "keep_away": ("KEEP_AWAY", int)}),
    }
    for name in secs:
        if name not in spec:
            raise data.DataError(f"data/enemies.toml [{name}]: такого врага нет в коде; есть: {', '.join(spec)}")
    for name, (cls, own) in spec.items():
        if name not in secs:
            raise data.DataError(f"data/enemies.toml: нет раздела [{name}]")
        sec = secs[name]
        if name == "archer":
            Arrow.DAMAGE = sec.get("arrow_damage", int, Arrow.DAMAGE)
            Arrow.REFLECTED_DAMAGE = sec.get("reflected_damage", int, Arrow.REFLECTED_DAMAGE)
        data.apply(cls, sec, dict(_COMMON, **own))
        lo, hi = cls.silver
        if lo > hi:
            raise data.DataError(f"{sec.where('silver')}: [от, до] — первое число не может быть больше второго")


_load()
