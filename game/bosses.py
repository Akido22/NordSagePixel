"""Боссы. Ярл-драугр Хрёрек — владыка кургана.

Набор атак (каждая читается по позе и вспышке):
  * серия из трёх рубящих ударов — можно парировать, после парирования ярл оглушён;
  * прыжок с ударом оземь — по полу расходятся две ударные волны: перепрыгни или прокатись;
  * круговой удар (вторая фаза) — тело вспыхивает красным: щитом не отразить, уходи.
На половине здоровья ярл впадает в ярость: зовёт волков, атакует быстрее.
"""

import math
import random
from types import SimpleNamespace

import pyxel

from . import audio, gfx
from .config import TILE
from .enemies import Enemy, _sign
from .entities import draw_humanoid, draw_stun_stars, rect_overlap

JARL_AXE = SimpleNamespace(icon="axe", tint={"6": "5", "f": "6"})

JARL_TINT = {"a": "6", "e": "5", "2": "1", "5": "1", "7": "5"}
JARL_ARMOR = {"8": "1", "a": "a", "e": "5"}
JARL_HELMET = {"6": "5", "a": "a"}


def build_sprites():
    gfx.build_humanoid(gfx.BOSS_ROW, base_tint=JARL_TINT, armor_tint=JARL_ARMOR,
                       helmet=True, helmet_tint=JARL_HELMET)


class Shockwave:
    """Ударная волна по полу. Не отбивается; блок тратит силы, прыжок и перекат спасают."""

    w, h = 10, 8
    deflectable = False
    DAMAGE = 3

    def __init__(self, x, ground_y, vx):
        self.x = x - self.w / 2
        self.y = ground_y - self.h
        self.vx = vx
        self.dead = False
        self.hit = False
        self.life = 110

    def on_blocked(self, world, player):
        pass

    def update(self, world):
        self.life -= 1
        self.x += self.vx
        lvl = world.level
        front = self.x + (self.w if self.vx > 0 else 0)
        floor = int((self.y + self.h + 1) // TILE)
        if (self.life <= 0 or lvl.is_solid(int(front // TILE), int((self.y + 4) // TILE))
                or not lvl.is_solid(int(front // TILE), floor)):
            self.dead = True
            return
        if pyxel.frame_count % 3 == 0:
            world.dust(self.x + self.w / 2, self.y + self.h, 1)
        p = world.player
        if not self.hit and not p.dead and rect_overlap(self.x, self.y, self.w, self.h, p):
            result = p.take_damage(self.DAMAGE, p.cx - _sign(self.vx) * 10, world,
                                   parryable=False, source=self)
            if result != "miss":
                self.hit = True

    def draw(self):
        t = pyxel.frame_count
        b = self.y + self.h
        for i in range(4):
            x = self.x + i * 3
            h = 3 + ((t // 2 + i * 3) % 6)
            pyxel.line(x, b - 1, x, b - h, 6 if i % 2 else 7)
        pyxel.line(self.x, b - 1, self.x + self.w - 1, b - 1, 5)


class JarlBoss(Enemy):
    name = "ЯРЛ-ДРАУГР ХРЁРЕК"
    subtitle = "Владыка кургана"
    flag = "boss:jarl"
    w = 16
    h = 30
    max_hp = 70
    contact_dmg = 2
    knock = 0
    silver = (12, 12)
    CHAIN_DMG = 4
    SLAM_DMG = 5
    SWEEP_DMG = 5

    def __init__(self, x, y):
        super().__init__(x, y)
        self.state = "sleep"
        self.state_t = 0
        self.phase = 1
        self.combo_n = 0
        self.struck = False
        self.attack_cd = 30
        self.dying = False
        self.leap_t = 0
        build_sprites()

    # ------------------------------------------------------------ свойства
    @property
    def awake(self):
        return self.state not in ("sleep",) and not self.dead

    @property
    def speed(self):
        return 1.3 if self.phase == 2 else 1.0

    def vulnerable(self):
        return self.state not in ("sleep", "rise", "roar") and not self.dying

    def _set(self, state, t=0):
        self.state = state
        self.state_t = int(t)

    # ------------------------------------------------------------ урон
    def take_hit(self, dmg, direction, world, heavy=False, plunge=False):
        if not self.vulnerable():
            world.sparks(self.cx - direction * 6, self.y + 12, 4)
            return "blocked"
        crit = self.stun_t > 0
        if crit:
            dmg = math.ceil(dmg * 2.5)
            self.stun_t = 0
            self._set("recover", 20)
            world.float_text(self.cx, self.y - 14, "КРИТ!", 10)
        self.hp -= dmg
        self.flash = 6
        world.float_text(self.cx, self.y - 4, str(dmg), 15 if crit else 10)
        world.sparks(self.cx - direction * 6, self.y + 12, 12 if crit or heavy else 6)
        world.freeze(7 if crit else 5 if heavy else 3)
        if crit or heavy:
            world.shake(3)
        if self.hp <= 0:
            self.hp = 0
            self.dying = True
            self._set("dying", 120)
            self.stun_t = 0
            audio.sfx(audio.ROAR)
            world.shake(8)
        elif self.phase == 1 and self.hp <= self.max_hp // 2:
            self._set("roar", 80)
            self.stun_t = 0
            audio.sfx(audio.HEAVY)
        else:
            audio.sfx(audio.HEAVY if crit or heavy else audio.HIT)
        return "hit"

    def on_parried(self, world, player):
        if self.state == "chain_strike":
            self.stun_t = 70 if self.phase == 1 else 50
            self._set("recover", 30)
            self.vx = 0

    def on_blocked(self, world, player):
        pass  # ярла щитом не оттолкнуть

    # ------------------------------------------------------------ цикл
    def update(self, world):
        self.anim_t += 1
        if self.flash > 0:
            self.flash -= 1
        if self.contact_cd > 0:
            self.contact_cd -= 1
        if self.dying:
            self._update_dying(world)
            return
        if self.stun_t > 0:
            self.stun_t -= 1
            self.vx *= 0.8
        else:
            self.think(world)
        self.apply_gravity()
        self.move(world.level, drop_through=True)
        p = world.player
        if (self.vulnerable() and not p.dead and self.contact_cd == 0 and self.stun_t == 0
                and rect_overlap(self.x + 3, self.y, self.w - 6, self.h, p)):
            if p.take_damage(self.contact_dmg, self.cx, world, parryable=False, source=self) != "miss":
                self.contact_cd = 40

    def _update_dying(self, world):
        self.state_t -= 1
        self.vx = 0
        if self.state_t % 12 == 0:
            world.smoke(self.cx + random.uniform(-8, 8), self.y + random.uniform(4, 26), 6)
            world.sparks(self.cx, self.y + 14, 4)
        if self.state_t <= 0:
            self.dead = True
            world.on_boss_defeated(self)

    def think(self, world):
        p = world.player
        dx = p.cx - self.cx
        dist = abs(dx)
        st = self.state
        if st == "sleep":
            if world.arena_trigger is not None and p.cx > world.arena_trigger and not p.dead:
                world.start_boss_fight(self)
                self._set("rise", 90)
            return
        if st == "rise":
            self.state_t -= 1
            if self.state_t == 45:
                audio.sfx(audio.ROAR)
                world.shake(6)
            if self.state_t <= 0:
                self._set("walk")
            return
        if st == "roar":
            self.vx = 0
            self.state_t -= 1
            if self.state_t == 60:
                audio.sfx(audio.ROAR)
                world.shake(8)
                world.float_text(self.cx, self.y - 14, "ЯРОСТЬ!", 8)
                self.phase = 2
                world.summon_wolves()
            if self.state_t <= 0:
                self._set("walk")
                self.attack_cd = 10
            return
        if st == "walk":
            self.facing = _sign(dx)
            if self.attack_cd > 0:
                self.attack_cd -= 1
            if p.dead:
                self.vx = 0
                return
            if self.attack_cd <= 0:
                if self.phase == 2 and dist < 44 and random.random() < 0.4:
                    self._set("sweep_wind", 40 / self.speed)
                    self.vx = 0
                    return
                if dist < 34:
                    self.combo_n = 0
                    self._set("chain_wind", 24 / self.speed)
                    self.vx = 0
                    return
                if dist > 70 or random.random() < 0.02:
                    self._set("leap_wind", 34 / self.speed)
                    self.vx = 0
                    return
            self.vx = self.facing * 0.55 * self.speed if dist > 26 else 0
            return
        if st == "chain_wind":
            self.vx = 0
            self.state_t -= 1
            if self.state_t <= 0:
                self._set("chain_strike", 9)
                self.struck = False
                self.vx = self.facing * 1.2
                audio.sfx(audio.SWING)
            return
        if st == "chain_strike":
            self.vx *= 0.8
            self.state_t -= 1
            reach = 26
            hx = self.x + self.w if self.facing > 0 else self.x - reach
            if not self.struck and rect_overlap(hx, self.y + 4, reach, self.h - 4, p):
                if p.take_damage(self.CHAIN_DMG, self.cx, world, source=self) != "miss":
                    self.struck = True
            if self.state == "chain_strike" and self.state_t <= 0:
                self.combo_n += 1
                if self.combo_n < 3:
                    self.facing = _sign(dx)
                    self._set("chain_wind", 15 / self.speed)
                else:
                    self._set("recover", 50 / self.speed)
            return
        if st == "leap_wind":
            self.vx = 0
            self.state_t -= 1
            if self.state_t <= 0:
                air = 2 * 5.2 / 0.22
                self.vx = max(-3.0, min(3.0, dx / air))
                self.vy = -5.2
                self.leap_t = 0
                self._set("leap")
                audio.sfx(audio.JUMP)
            return
        if st == "leap":
            self.leap_t += 1
            if self.leap_t > 6 and self.on_ground:
                self._slam(world)
            return
        if st == "sweep_wind":
            self.vx = 0
            self.state_t -= 1
            if self.state_t <= 0:
                self._set("sweep", 18)
                self.struck = False
                audio.sfx(audio.HEAVY)
            return
        if st == "sweep":
            self.state_t -= 1
            reach = 30
            if not self.struck and rect_overlap(self.x - reach, self.y + 4, self.w + reach * 2, self.h - 4, p):
                if p.take_damage(self.SWEEP_DMG, self.cx, world, parryable=False, source=self) != "miss":
                    self.struck = True
            if self.state_t <= 0:
                self._set("recover", 45 / self.speed)
            return
        if st == "recover":
            self.vx *= 0.7
            self.state_t -= 1
            if self.state_t <= 0:
                self._set("walk")
                self.attack_cd = 24 if self.phase == 1 else 12

    def _slam(self, world):
        self.vx = 0
        ground = self.y + self.h
        audio.sfx(audio.SLAM)
        world.shake(7)
        world.dust(self.cx, ground, 12)
        speed = 2.8 if self.phase == 2 else 2.3
        world.projectiles.append(Shockwave(self.cx - 10, ground, -speed))
        world.projectiles.append(Shockwave(self.cx + 10, ground, speed))
        p = world.player
        if rect_overlap(self.x - 6, ground - 12, self.w + 12, 12, p):
            p.take_damage(self.SLAM_DMG, self.cx, world, parryable=False, source=self)
        self._set("recover", 46 / self.speed)

    # ------------------------------------------------------------ отрисовка
    def pose(self):
        st = self.state
        t = self.anim_t
        if st in ("sleep", "rise", "roar", "dying"):
            return gfx.F_IDLE[0], None
        if st == "chain_wind":
            return gfx.F_ATTACK, -115
        if st == "chain_strike":
            return gfx.F_ATTACK, 60 if self.combo_n % 2 == 0 else -40
        if st == "leap_wind":
            return gfx.F_IDLE[1], -100
        if st == "leap":
            return (gfx.F_JUMP if self.vy < 0 else gfx.F_FALL), -100
        if st == "sweep_wind":
            return gfx.F_ATTACK, -140
        if st == "sweep":
            return gfx.F_ATTACK, (t * 40) % 360
        if st == "recover":
            return gfx.F_IDLE[0], 30
        moving = abs(self.vx) > 0.05
        return (gfx.F_RUN[(t // 10) % 4] if moving else gfx.F_IDLE[(pyxel.frame_count // 30) % 2]), None

    def draw(self):
        frame, angle = self.pose()
        st = self.state
        t = self.anim_t
        # Цвет глаз: тлеют во сне, синие в первой фазе, красные в ярости.
        if st == "sleep" or (st == "rise" and (self.state_t // 4) % 2 and self.state_t > 45):
            pyxel.pal(12, 1)
        elif self.phase == 2 or (st == "roar" and self.state_t < 60):
            pyxel.pal(12, 8)
        # Предупреждения: золото — прыжок, красная вспышка — круговой удар.
        if st == "leap_wind" and (self.state_t // 3) % 2:
            for c in (1, 5):
                pyxel.pal(c, 10)
        if st == "sweep_wind" and (self.state_t // 3) % 2:
            for c in range(1, 16):
                pyxel.pal(c, 8)
        dy = 2 if st == "leap_wind" else 0
        if st == "dying":
            dy = min(10, (120 - self.state_t) // 10)
            if (t // 3) % 2:
                for c in range(1, 16):
                    pyxel.pal(c, 7)
        shake = random.randint(-1, 1) if st in ("roar", "rise") and self.state_t < 60 else 0
        draw_humanoid(gfx.BOSS_ROW, frame, self.x + shake, self.y + dy, self.facing,
                      weapon=JARL_AXE, weapon_angle=angle, flash=self.flash > 0, scale=2)
        pyxel.pal()
        if self.stun_t > 0:
            draw_stun_stars(self.cx, self.y - 8)
