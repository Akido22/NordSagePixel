"""Враги: волк, драугр, драугр со щитом, драугр-лучник, стрелы и тренировочное чучело.

Общее правило боя: каждая атака врага заметно «предупреждает» о себе (присед, замах,
натянутая тетива), её можно заблокировать щитом, а поднятым в нужный момент щитом —
парировать. Парированный враг оглушён, и следующий удар по нему критический.
"""

import math
from types import SimpleNamespace

import pyxel

from . import audio, gfx
from .config import TILE
from .entities import Body, draw_humanoid, draw_stun_stars, overlap, rect_overlap


def _sign(v):
    return 1 if v >= 0 else -1


class Enemy(Body):
    max_hp = 3
    contact_dmg = 1
    knock = 2.0
    silver = (1, 2)
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
    w = 14
    h = 9
    max_hp = 4
    contact_dmg = 1
    lunge_dmg = 3
    knock = 2.4
    silver = (1, 3)
    CROUCH = 20

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
                self.lunge_cd = 90
            return
        if not self.on_ground:
            return
        p = world.player
        if self.player_near(world, 110):
            self.facing = _sign(p.cx - self.cx)
            if not self.ground_ahead(world.level, self.facing):
                self.vx = 0
            elif abs(p.cx - self.cx) < 44 and self.lunge_cd == 0:
                self.crouch_t = self.CROUCH
                self.vx = 0
            else:
                self.vx = self.facing * 1.25
        else:
            self.patrol(world, 0.5)

    def draw(self):
        if self.flash:
            for c in range(1, 16):
                pyxel.pal(c, 15)
        elif self.crouch_t and (self.crouch_t // 3) % 2:
            pyxel.pal(10, 8)  # глаза вспыхивают красным
        moving = abs(self.vx) > 0.1
        spr = gfx.SPR_WOLF[(self.anim_t // 8) % 2 if moving else 0]
        if not self.on_ground:
            spr = gfx.SPR_WOLF[1]
        dy = 2 if self.crouch_t else 0
        gfx.sprite(spr, self.x - 1, self.y - 1 + dy, flip=self.facing < 0)
        pyxel.pal()
        self.draw_status()


# ===================================================================== драугры
RUSTY_SWORD = SimpleNamespace(icon="sword", tint={"f": "6", "6": "5", "a": "2"})
RUSTY_SHIELD = SimpleNamespace(shield_colors=(1, 5, 6))


class Draugr(Enemy):
    w = 8
    h = 15
    max_hp = 8
    contact_dmg = 1
    strike_dmg = 4
    knock = 1.3
    silver = (3, 5)
    stun_time = 90
    REACH = 16
    WINDUP = 34

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
            if self.player_near(world, 120, 24):
                self.facing = _sign(p.cx - self.cx)
                if abs(p.cx - self.cx) < 20:
                    self._set("windup", self.WINDUP)
                    self.vx = 0
                elif self.ground_ahead(world.level, self.facing):
                    self.vx = self.facing * 0.55
                else:
                    self.vx = 0
            else:
                self.patrol(world, 0.3)
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
                self._set("recover", 40)
            else:
                self._set("walk", 0)

    def pose(self):
        """(кадр, угол оружия) для текущего состояния."""
        if self.state == "strike":
            return gfx.F_ATTACK, 56
        if self.state == "windup":
            return gfx.F_ATTACK, -95
        moving = abs(self.vx) > 0.05
        return (gfx.F_RUN[(self.anim_t // 10) % 4] if moving else gfx.F_IDLE[0]), None

    def draw(self, shield=None, shield_front=False):
        frame, angle = self.pose()
        if self.state == "windup" and (self.state_t // 4) % 2:
            pyxel.pal(15, 8)  # глаза вспыхивают перед ударом
        draw_humanoid(gfx.DRAUGR_ROW, frame, self.x, self.y, self.facing, weapon=RUSTY_SWORD,
                      shield=shield, shield_front=shield_front, weapon_angle=angle,
                      flash=self.flash > 0)
        pyxel.pal()
        self.draw_status()


class ShieldDraugr(Draugr):
    """Держит щит перед собой: лёгкие удары спереди отскакивают.

    Пробивают его тяжёлый удар, удар сверху, удар в спину, парирование
    или серия лёгких ударов, которая ломает стойку.
    """

    max_hp = 10
    silver = (4, 6)
    GUARD_MAX = 3

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
            if self.guard_regen >= 120:
                self.guard += 1
                self.guard_regen = 0
        super().think(world)

    def draw(self):
        super().draw(shield=RUSTY_SHIELD, shield_front=self.guarding())


class Archer(Enemy):
    """Драугр-лучник: держит дистанцию и стреляет, предупреждая натянутой тетивой."""

    w = 8
    h = 15
    max_hp = 4
    contact_dmg = 1
    knock = 2.2
    silver = (2, 4)
    stun_time = 90
    AIM = 44

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
                world.projectiles.append(Arrow(self.cx + self.facing * 6, self.y + 7, self.facing * 2.8))
                audio.sfx(audio.BOW)
                self.state = "walk"
                self.cooldown = 50
            return
        if not self.player_near(world, 150, 40):
            self.patrol(world, 0.3)
            return
        dist = abs(p.cx - self.cx)
        self.facing = _sign(p.cx - self.cx)
        if dist < 48 and self.ground_ahead(world.level, -self.facing):
            self.vx = -self.facing * 0.7  # пятится, не сводя глаз с героя
        elif dist > 130 and self.ground_ahead(world.level, self.facing):
            self.vx = self.facing * 0.5
        else:
            self.vx = 0
            if self.cooldown == 0:
                self.state = "aim"
                self.state_t = self.AIM

    def draw(self):
        pyxel.pal(2, 3)  # зелёный истлевший плащ
        if self.flash:
            for c in range(1, 16):
                pyxel.pal(c, 15)
        aiming = self.state == "aim"
        frame = gfx.F_BLOCK if aiming else (gfx.F_RUN[(self.anim_t // 10) % 4] if abs(self.vx) > 0.05
                                            else gfx.F_IDLE[0])
        draw_humanoid(gfx.DRAUGR_ROW, frame, self.x, self.y, self.facing)
        pyxel.pal()
        # Лук в вытянутой руке.
        hx = self.cx + self.facing * 7
        hy = self.y + 7
        f = self.facing
        pyxel.line(hx, hy - 5, hx + f * 2, hy - 2, 4)
        pyxel.line(hx + f * 2, hy - 2, hx + f * 2, hy + 2, 4)
        pyxel.line(hx + f * 2, hy + 2, hx, hy + 5, 4)
        pull = 3 if aiming else 0
        pyxel.line(hx, hy - 5, hx - f * pull, hy, 7)
        pyxel.line(hx - f * pull, hy, hx, hy + 5, 7)
        if aiming:
            pyxel.line(hx - f * pull, hy, hx + f * 4, hy, 4)
            if self.state_t < 14 and (self.state_t // 2) % 2:
                pyxel.pset(hx + f * 5, hy, 15)  # блеск наконечника: сейчас выстрелит
        self.draw_status()


class Arrow:
    w, h = 6, 2
    DAMAGE = 2

    def __init__(self, x, y, vx):
        self.x = x - self.w / 2
        self.y = y
        self.vx = vx
        self.hostile = True
        self.dead = False
        self.life = 200

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
                    e.take_hit(3, _sign(self.vx), world)
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

    w = 10
    h = 18
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
        pyxel.rect(cx - 1, b - 20, 2, 20, 2)  # кол
        top = cx + lean
        pyxel.line(top - 7, b - 15, top + 7, b - 15, 4)  # руки-перекладина
        pyxel.pset(top - 8, b - 16, 10)
        pyxel.pset(top + 8, b - 16, 10)
        pyxel.elli(top - 5, b - 15, 10, 11, 10)  # соломенное тулово
        pyxel.line(top - 4, b - 10, top + 4, b - 10, 4)  # опояска
        pyxel.circ(top, b - 19, 3, 7)  # мешок-голова
        pyxel.pset(top - 1, b - 20, 1)
        pyxel.pset(top + 1, b - 20, 1)
        pyxel.line(top - 1, b - 18, top + 1, b - 18, 8)
        pyxel.pal()
