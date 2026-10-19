"""Игровые сущности: герой, враги, предметы и объекты уровня."""

import math
from types import SimpleNamespace

import pyxel

from . import audio, controls, gfx, items, ui
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


# ===================================================================== герой
FIST = SimpleNamespace(id="fist", icon=None, atk=0, reach=9, swing=14, tint={})


class Player(Body):
    w = 8
    h = 15
    ACCEL = 0.28
    AIR_ACCEL = 0.18
    MAX_SPEED = 1.35
    JUMP_V = -4.1
    COYOTE = 6
    JUMP_BUFFER = 7
    INVULN = 70

    def __init__(self, x, y, inventory):
        super().__init__(x, y)
        self.inv = inventory
        self.hp = inventory.max_hp
        self.facing = 1
        self.anim_t = 0
        self.attack_t = 0
        self.attack_dur = 1
        self.hit_ids = set()
        self.invuln = 0
        self.coyote = 0
        self.jump_buf = 0
        self.drop_t = 0
        self.dead = False
        self.safe_pos = (x, y)
        self.flash = 0
        self.rebuild_look()

    # ------------------------------------------------------------ внешний вид
    def rebuild_look(self):
        armor = self.inv.equipped("armor")
        helmet = self.inv.equipped("helmet")
        gfx.build_humanoid(
            gfx.HERO_ROW,
            armor_tint=armor.body_tint if armor else {"8": "7", "a": "7"},
            helmet=helmet is not None,
            helmet_tint=helmet.helmet_tint if helmet else None,
        )
        self.hp = min(self.hp, self.inv.max_hp)

    @property
    def weapon(self):
        return self.inv.equipped("weapon") or FIST

    # ------------------------------------------------------------ логика
    def update(self, world):
        level = world.level
        if self.dead:
            self.apply_gravity()
            self.vx *= 0.9
            self.move(level)
            return

        attacking = self.attack_t > 0
        direction = int(controls.held("right")) - int(controls.held("left"))
        if direction and not attacking:
            self.facing = direction
        accel = self.ACCEL if self.on_ground else self.AIR_ACCEL
        top = self.MAX_SPEED * (0.45 if attacking and self.on_ground else 1.0)
        if direction:
            self.vx += direction * accel
            self.vx = max(-top, min(top, self.vx))
        else:
            if abs(self.vx) <= accel:
                self.vx = 0
            else:
                self.vx -= accel * (1 if self.vx > 0 else -1)

        # --- прыжок (с «койотом» и буфером нажатия)
        if controls.pressed("jump"):
            self.jump_buf = self.JUMP_BUFFER
        if self.jump_buf > 0 and (self.on_ground or self.coyote > 0):
            if controls.held("down") and self.on_platform:
                self.drop_t = 10
            else:
                self.vy = self.JUMP_V
                self.coyote = 0
                audio.sfx(audio.JUMP)
                world.dust(self.cx, self.y + self.h)
            self.jump_buf = 0
        if self.jump_buf > 0:
            self.jump_buf -= 1
        if self.vy < -1.6 and not controls.held("jump"):
            self.vy = -1.6

        self.apply_gravity()
        was_on_ground = self.on_ground
        self.move(level, drop_through=self.drop_t > 0)
        if self.drop_t > 0:
            self.drop_t -= 1
        if self.on_ground:
            self.coyote = self.COYOTE
            if not was_on_ground and self.vy == 0:
                world.dust(self.cx, self.y + self.h, 3)
        elif self.coyote > 0:
            self.coyote -= 1

        # --- удар
        if controls.pressed("attack") and self.attack_t == 0:
            self.attack_dur = self.weapon.swing
            self.attack_t = self.attack_dur
            self.hit_ids.clear()
            audio.sfx(audio.SWING)
        if self.attack_t > 0:
            if self.attack_active():
                hx, hy, hw, hh = self.attack_box()
                for enemy in world.enemies:
                    if id(enemy) not in self.hit_ids and not enemy.dead and rect_overlap(hx, hy, hw, hh, enemy):
                        self.hit_ids.add(id(enemy))
                        enemy.take_hit(self.inv.attack, self.facing, world)
            self.attack_t -= 1

        if self.invuln > 0:
            self.invuln -= 1
        if self.flash > 0:
            self.flash -= 1
        self.anim_t += 1

        # --- колья и падение за край мира
        if level.touches_spikes(self.x, self.y, self.w, self.h) or self.y > level.pixel_h:
            self.hurt_by_hazard(world)
        elif self.on_ground and not self.on_platform:
            l_ok = level.is_solid(int(self.x // TILE), int((self.y + self.h) // TILE))
            r_ok = level.is_solid(int((self.x + self.w - 0.01) // TILE), int((self.y + self.h) // TILE))
            if l_ok and r_ok:
                self.safe_pos = (self.x, self.y)

    def attack_progress(self):
        return 1 - self.attack_t / max(1, self.attack_dur)

    def attack_active(self):
        return self.attack_t > 0 and 0.2 <= self.attack_progress() <= 0.75

    def attack_box(self):
        reach = self.weapon.reach
        hx = self.x + self.w if self.facing > 0 else self.x - reach
        return hx, self.y - 2, reach, self.h

    def take_damage(self, dmg, from_x, world):
        if self.invuln > 0 or self.dead:
            return
        defense = self.inv.defense
        actual = max(1, math.ceil(dmg * 6 / (6 + defense)))
        self.hp -= actual
        self.invuln = self.INVULN
        self.flash = 8
        knock = 1 if self.cx >= from_x else -1
        self.vx = knock * 2.2
        self.vy = -2.2
        world.float_text(self.cx, self.y - 4, f"-{actual}", 8)
        world.shake(4)
        if self.hp <= 0:
            self.hp = 0
            self.dead = True
            audio.sfx(audio.DEATH)
        else:
            audio.sfx(audio.HURT)

    def hurt_by_hazard(self, world):
        was_invuln = self.invuln
        self.invuln = 0
        self.take_damage(2, self.cx, world)
        if not self.dead:
            self.x, self.y = self.safe_pos
            self.vx = self.vy = 0
            self.invuln = max(self.invuln, was_invuln)

    def heal(self, amount):
        before = self.hp
        self.hp = min(self.inv.max_hp, self.hp + amount)
        return self.hp - before

    # ------------------------------------------------------------ отрисовка
    def frame(self):
        if self.attack_t > 0:
            return gfx.F_ATTACK if self.on_ground else gfx.F_ATTACK_AIR
        if not self.on_ground:
            return gfx.F_JUMP if self.vy < 0 else gfx.F_FALL
        if abs(self.vx) > 0.2:
            return gfx.F_RUN[(self.anim_t // 6) % 4]
        return gfx.F_IDLE[(pyxel.frame_count // 32) % 2]

    def draw(self):
        if self.invuln > 0 and not self.dead and (self.invuln // 3) % 2:
            return
        draw_humanoid(
            gfx.HERO_ROW, self.frame(), self.x, self.y, self.facing,
            weapon=self.weapon if self.weapon is not FIST else None,
            shield=self.inv.equipped("shield"),
            attack_p=self.attack_progress() if self.attack_t > 0 else None,
            flash=self.flash > 0,
        )
        if self.attack_active() and self.weapon is not FIST:
            draw_slash(self)


def draw_humanoid(row, frame, x, y, facing, weapon=None, shield=None, attack_p=None, flash=False, scale=1):
    """Рисует гуманоида со щитом и оружием. (x, y) — левый верхний угол хитбокса 8x15."""
    sx = x - 4 * scale
    sy = y - 5 * scale

    def fx(px):
        return px if facing > 0 else gfx.FRAME_W - 1 - px

    if flash:
        for c in range(1, 16):
            pyxel.pal(c, 15)
    if shield:
        gfx.shield(shield, sx + (fx(5) + 0.5) * scale, sy + 13 * scale, scale)
    gfx.humanoid(row, frame, sx, sy, flip=facing < 0, scale=scale)
    if weapon:
        if attack_p is not None:
            hand = gfx.HAND_ATTACK
            angle = -80 + attack_p * 170
        else:
            hand = gfx.HAND_IDLE
            angle = -10
        gfx.weapon(weapon, sx + (fx(hand[0]) + 0.5) * scale, sy + (hand[1] + 0.5) * scale, facing, angle, scale)
    if flash:
        pyxel.pal()


def draw_slash(player):
    p = player.attack_progress()
    gx = player.x + player.w / 2 + player.facing * 4
    gy = player.y + 7
    r = player.weapon.reach + 2
    a1 = -80 + p * 170
    for i in range(10):
        a = math.radians(a1 - 45 - i * 6)
        px = gx + math.cos(a) * r * player.facing
        py = gy + math.sin(a) * r
        pyxel.pset(px, py, 15 if i < 4 else 7)


# ===================================================================== враги
class Enemy(Body):
    max_hp = 3
    contact_dmg = 1
    knock = 2.0
    silver = (1, 2)

    def __init__(self, x, y):
        super().__init__(x, y)
        self.hp = self.max_hp
        self.facing = -1
        self.dead = False
        self.hurt_t = 0
        self.flash = 0
        self.anim_t = 0

    def take_hit(self, dmg, direction, world):
        self.hp -= dmg
        self.hurt_t = 14
        self.flash = 6
        self.vx = direction * self.knock
        self.vy = -1.6
        self.facing = -direction
        world.float_text(self.cx, self.y - 4, str(dmg), 10)
        world.sparks(self.cx - direction * 3, self.cy, 6)
        if self.hp <= 0:
            self.dead = True
            audio.sfx(audio.KILL)
            world.on_enemy_killed(self)
        else:
            audio.sfx(audio.HIT)

    def update(self, world):
        self.anim_t += 1
        if self.flash > 0:
            self.flash -= 1
        if self.hurt_t > 0:
            self.hurt_t -= 1
            self.vx *= 0.88
        else:
            self.think(world)
        self.apply_gravity()
        self.move(world.level)
        player = world.player
        if not player.dead and overlap(self, player) and self.hurt_t == 0:
            player.take_damage(self.contact_dmg, self.cx, world)

    def think(self, world):
        pass

    def player_near(self, world, dist_x, dist_y=28):
        p = world.player
        return not p.dead and abs(p.cx - self.cx) < dist_x and abs(p.cy - self.cy) < dist_y

    def patrol(self, world, speed):
        if self.hit_wall or (self.on_ground and not self.ground_ahead(world.level, self.facing)):
            self.facing = -self.facing
        self.vx = self.facing * speed


class Wolf(Enemy):
    w = 14
    h = 9
    max_hp = 4
    contact_dmg = 2
    knock = 2.4
    silver = (1, 3)

    def __init__(self, x, y):
        super().__init__(x, y)
        self.lunge_cd = 0

    def think(self, world):
        if self.lunge_cd > 0:
            self.lunge_cd -= 1
        if not self.on_ground:
            return
        p = world.player
        if self.player_near(world, 110):
            self.facing = 1 if p.cx > self.cx else -1
            if not self.ground_ahead(world.level, self.facing):
                self.vx = 0
            elif abs(p.cx - self.cx) < 40 and self.lunge_cd == 0:
                self.vx = self.facing * 2.4
                self.vy = -2.6
                self.lunge_cd = 80
            else:
                self.vx = self.facing * 1.25
        else:
            self.patrol(world, 0.5)

    def draw(self):
        if self.flash:
            for c in range(1, 16):
                pyxel.pal(c, 15)
        moving = abs(self.vx) > 0.1
        spr = gfx.SPR_WOLF[(self.anim_t // 8) % 2 if moving else 0]
        if not self.on_ground:
            spr = gfx.SPR_WOLF[1]
        gfx.sprite(spr, self.x - 1, self.y - 1, flip=self.facing < 0)
        pyxel.pal()


RUSTY_SWORD = SimpleNamespace(icon="sword", tint={"f": "6", "6": "5", "a": "2"})


class Draugr(Enemy):
    w = 8
    h = 15
    max_hp = 8
    contact_dmg = 1
    strike_dmg = 4
    knock = 1.3
    silver = (3, 5)
    REACH = 16

    def __init__(self, x, y):
        super().__init__(x, y)
        self.state = "walk"
        self.state_t = 0
        self.struck = False

    def think(self, world):
        p = world.player
        if self.state == "walk":
            if self.player_near(world, 120, 24):
                self.facing = 1 if p.cx > self.cx else -1
                if abs(p.cx - self.cx) < 20:
                    self._set("windup", 34)
                    self.vx = 0
                elif self.ground_ahead(world.level, self.facing):
                    self.vx = self.facing * 0.55
                else:
                    self.vx = 0
            else:
                self.patrol(world, 0.3)
        else:
            self.vx = 0
            self.state_t -= 1
            if self.state == "strike" and not self.struck and not p.dead:
                hx = self.x + self.w if self.facing > 0 else self.x - self.REACH
                if rect_overlap(hx, self.y, self.REACH, self.h, p):
                    p.take_damage(self.strike_dmg, self.cx, world)
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

    def _set(self, state, t):
        self.state = state
        self.state_t = t

    def take_hit(self, dmg, direction, world):
        super().take_hit(dmg, direction, world)
        if self.state == "windup":
            self._set("recover", 20)  # удар сбивает замах

    def draw(self):
        if self.state in ("strike",):
            frame, p = gfx.F_ATTACK, 0.8
        elif self.state == "windup":
            frame, p = gfx.F_ATTACK, 0.0
        else:
            frame, p = (gfx.F_RUN[(self.anim_t // 10) % 4] if abs(self.vx) > 0.05 else gfx.F_IDLE[0]), None
        if self.state == "windup" and (self.state_t // 4) % 2:
            pyxel.pal(15, 8)  # глаза вспыхивают перед ударом
        draw_humanoid(gfx.DRAUGR_ROW, frame, self.x, self.y, self.facing,
                      weapon=RUSTY_SWORD, attack_p=p, flash=self.flash > 0)
        pyxel.pal()


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
        self.w, self.h = (40, 56) if style == "town" else (24, 32)
        self.x = tx * TILE + 4 - self.w // 2
        self.y = (ty + 1) * TILE - self.h
        self.target = target
        self.spawn = spawn

    def draw(self):
        if self.style == "town":
            self._draw_town()
        else:
            self._draw_forest()

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
