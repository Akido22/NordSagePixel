"""Герой: движение и бой — выносливость, перекат, блок и парирование, серии ударов."""

import math
from types import SimpleNamespace

import pyxel

from . import audio, controls, data, spells, sprites
from .config import TILE
from .entities import Body, draw_humanoid, draw_stun_stars, rect_overlap

FIST = SimpleNamespace(id="fist", icon=None, atk=0, reach=9, swing=14, stamina=8, tint={})

# Числа боя и движения — в data/player.toml.
_D = data.load("player.toml")
_mv = data.Section("player.toml", "movement", _D.get("movement", {}))
_sm = data.Section("player.toml", "stamina", _D.get("stamina", {}))
_cb = data.Section("player.toml", "combat", _D.get("combat", {}))
_mg = data.Section("player.toml", "magic", _D.get("magic", {}))

STAMINA_REGEN = _sm.get("regen", float)  # в кадр
STAMINA_DELAY = _sm.get("delay", int)  # пауза перед восстановлением после траты
EXHAUST_DELAY = _sm.get("exhaust_delay", int)  # пауза, если силы кончились совсем
ROLL_COST = _sm.get("roll_cost", int)
HEAVY_COST = _sm.get("heavy_cost", int)
PLUNGE_COST = _sm.get("plunge_cost", int)
PARRY_WINDOW = _cb.get("parry_window", int)  # кадров после поднятия щита, когда удар парируется
BLOCK_COOLDOWN = _cb.get("block_cooldown", int)  # нельзя сразу снова поднять щит (иначе парирование — спам)
CHARGE_TIME = _cb.get("charge_frames", int)  # кадров удержания после взмаха для тяжёлого удара
COMBO_MAX = _cb.get("combo_max", int)
INPUT_BUFFER = _cb.get("input_buffer", int)  # кадров, сколько помнится нажатие (в т.ч. во время стоп-кадра)
MANA_REGEN = _mg.get("mana_regen", float)  # в кадр


class Player(Body):
    w = 10
    h = 22
    ACCEL = 0.28
    AIR_ACCEL = 0.18
    MAX_SPEED = _mv.get("max_speed", float)
    JUMP_V = -_mv.get("jump_velocity", float)
    COYOTE = _mv.get("coyote_frames", int)
    JUMP_BUFFER = _mv.get("jump_buffer", int)
    INVULN = _cb.get("invuln_frames", int)
    ROLL_TIME = _cb.get("roll_frames", int)
    ROLL_IFRAMES = tuple(_cb.get("roll_iframes", list))
    for _sec in (_mv, _sm, _cb, _mg):
        _sec.check_unknown()

    def __init__(self, x, y, inventory):
        super().__init__(x, y)
        self.inv = inventory
        self.hp = inventory.max_hp
        self.facing = 1
        self.anim_t = 0
        self.state = "move"  # move, attack, charge, plunge, roll, block, stun, recover
        self.state_t = 0
        self.attack_kind = None  # light, heavy, air, plunge
        self.attack_t = 0
        self.attack_dur = 1
        self.combo = 0
        self.queued = 0  # сколько ударов серии ждут своей очереди
        self.charge = 0
        self.hit_ids = set()
        self.block_t = 0
        self.block_cd = 0
        self.stamina = inventory.max_stamina
        self.mana = float(inventory.max_mana)
        self.shield_t = 0  # щит Перуна
        self.cast_spell = None
        self.buf_cast = 0
        self.stamina_wait = 0
        self.stamina_flash = 0
        self.invuln = 0
        self.coyote = 0
        self.jump_buf = 0
        self.buf_attack = 0
        self.buf_roll = 0
        self.drop_t = 0
        self.dead = False
        self.safe_pos = (x, y)
        self.flash = 0
        self.dead_t = 0
        self.look = []
        self.rebuild_look()

    # ------------------------------------------------------------ внешний вид
    def rebuild_look(self):
        self.look = sprites.hero_look(self.inv)
        self.hp = min(self.hp, self.inv.max_hp)

    @property
    def weapon(self):
        return self.inv.equipped("weapon") or FIST

    @property
    def stamina_max(self):
        return self.inv.max_stamina

    # ------------------------------------------------------------ выносливость
    def spend(self, amount):
        self.stamina = max(0.0, self.stamina - amount)
        self.stamina_wait = EXHAUST_DELAY if self.stamina <= 0 else STAMINA_DELAY

    def can_act(self):
        """Действие разрешено, пока есть хоть немного сил (как в souls-играх)."""
        if self.stamina > 0:
            return True
        self.stamina_flash = 20
        return False

    def _regen(self):
        if self.stamina_wait > 0:
            self.stamina_wait -= 1
            return
        rate = STAMINA_REGEN * (0.35 if self.state == "block" else 1.0)
        self.stamina = min(self.stamina_max, self.stamina + rate)

    def _regen_mana(self):
        self.mana = min(self.inv.max_mana, self.mana + MANA_REGEN)

    # ------------------------------------------------------------ ввод
    def poll_input(self):
        """Запоминает нажатия. Вызывается каждый кадр, даже во время стоп-кадра."""
        if controls.pressed("attack"):
            self.buf_attack = INPUT_BUFFER
        if controls.pressed("roll"):
            self.buf_roll = INPUT_BUFFER
        if controls.pressed("jump"):
            self.jump_buf = self.JUMP_BUFFER
        if controls.pressed("cast"):
            self.buf_cast = INPUT_BUFFER

    def _take(self, name):
        """Забирает запомненное нажатие ("attack" или "roll")."""
        attr = "buf_" + name
        if getattr(self, attr) > 0:
            setattr(self, attr, 0)
            return True
        return False

    # ------------------------------------------------------------ логика
    def update(self, world):
        level = world.level
        if self.dead:
            self.dead_t += 1
            self.apply_gravity()
            self.vx *= 0.9
            self.move(level)
            return

        self._regen()
        self._regen_mana()
        for name in ("invuln", "flash", "stamina_flash", "block_cd", "shield_t"):
            if getattr(self, name) > 0:
                setattr(self, name, getattr(self, name) - 1)
        self.anim_t += 1
        direction = int(controls.held("right")) - int(controls.held("left"))

        handler = getattr(self, "_st_" + self.state)
        handler(world, direction)
        for name in ("buf_attack", "buf_roll", "jump_buf", "buf_cast"):
            if getattr(self, name) > 0:
                setattr(self, name, getattr(self, name) - 1)

        if self.state != "plunge":
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

        if self.state == "plunge":
            self._plunge_contact(world)

        # --- колья и падение за край мира
        if level.touches_spikes(self.x, self.y, self.w, self.h) or self.y > level.pixel_h:
            self.hurt_by_hazard(world)
        elif self.on_ground and not self.on_platform:
            l_ok = level.is_solid(int(self.x // TILE), int((self.y + self.h) // TILE))
            r_ok = level.is_solid(int((self.x + self.w - 0.01) // TILE), int((self.y + self.h) // TILE))
            if l_ok and r_ok:
                self.safe_pos = (self.x, self.y)

    def _set(self, state, t=0):
        self.state = state
        self.state_t = t

    def _walk(self, direction, top_scale=1.0, turn=True):
        if direction and turn:
            self.facing = direction
        accel = self.ACCEL if self.on_ground else self.AIR_ACCEL
        top = self.MAX_SPEED * top_scale
        if direction:
            self.vx += direction * accel
            self.vx = max(-top, min(top, self.vx))
        else:
            self._brake(accel)

    def _brake(self, amount):
        if abs(self.vx) <= amount:
            self.vx = 0
        else:
            self.vx -= amount * (1 if self.vx > 0 else -1)

    # --- обычное движение и начало действий
    def _st_move(self, world, direction):
        self._walk(direction)
        if self.jump_buf > 0 and (self.on_ground or self.coyote > 0):
            if controls.held("down") and self.on_platform:
                self.drop_t = 10
            else:
                self.vy = self.JUMP_V
                self.coyote = 0
                audio.sfx(audio.JUMP)
                world.dust(self.cx, self.y + self.h)
            self.jump_buf = 0
        if self.vy < -1.6 and not controls.held("jump"):
            self.vy = -1.6

        if self.buf_roll and self.on_ground:
            self.buf_roll = 0
            if self.can_act():
                self._start_roll(world, direction)
        elif controls.held("block") and self.on_ground and self.block_cd == 0:
            self._set("block")
            self.block_t = 0
        elif self._take("cast"):
            self._start_cast(world)
        elif self._take("attack"):
            if self.can_act():
                if not self.on_ground and controls.held("down"):
                    self._start_attack(world, "plunge")
                else:
                    self.combo = 0
                    self._start_attack(world, "light" if self.on_ground else "air")

    # --- чары
    def _start_cast(self, world):
        rune = self.inv.spell
        if rune is None:
            world.toast("Ты не знаешь ни одной руны", 6)
            audio.sfx(audio.DENY)
            return
        spell = spells.SPELLS[rune]
        if spell.ground_only and not self.on_ground:
            audio.sfx(audio.DENY)
            return
        if self.mana < spell.cost:
            world.toast("Не хватает маны", 12)
            audio.sfx(audio.DENY)
            return
        self.mana -= spell.cost
        self.cast_spell = rune
        self._set("cast", spell.cast)
        audio.sfx(audio.CHARGED)

    def _st_cast(self, world, direction):
        self._brake(0.3 if self.on_ground else 0.05)
        if not self.on_ground:
            self.vy = min(self.vy, 0.6)  # в воздухе чары чуть замедляют падение
        self.state_t -= 1
        if self.state_t <= 0:
            spells.release(self.cast_spell, self, world)
            self.cast_spell = None
            self._set("move")

    # --- перекат
    def _start_roll(self, world, direction):
        self.spend(ROLL_COST)
        if direction:
            self.facing = direction
        self._set("roll", self.ROLL_TIME)
        audio.sfx(audio.ROLL)
        world.dust(self.cx, self.y + self.h, 4)

    def rolling_invuln(self):
        if self.state != "roll":
            return False
        t = self.ROLL_TIME - self.state_t
        return self.ROLL_IFRAMES[0] <= t <= self.ROLL_IFRAMES[1]

    def _st_roll(self, world, direction):
        t = self.ROLL_TIME - self.state_t
        speed = 2.7 if t < 14 else 2.7 * max(0.0, (self.ROLL_TIME - t) / 8)
        self.vx = self.facing * speed
        self.state_t -= 1
        if self.state_t <= 0:
            self._set("move")

    # --- блок и парирование
    def _st_block(self, world, direction):
        self.block_t += 1
        self._brake(0.3)
        if not controls.held("block") or not self.on_ground:
            self.block_cd = BLOCK_COOLDOWN
            self._set("move")
        elif self._take("roll") and self.can_act():
            self.block_cd = BLOCK_COOLDOWN
            self._start_roll(world, direction)

    def _parry(self, world, source):
        audio.sfx(audio.PARRY)
        world.freeze(8)
        world.shake(2)
        fx = self.cx + self.facing * 8
        world.sparks(fx, self.y + 6, 14)
        world.float_text(fx, self.y - 6, "ПАРИРОВАНО", 10)
        self.stamina = min(self.stamina_max, self.stamina + 15)
        if source is not None and hasattr(source, "on_parried"):
            source.on_parried(world, self)

    # --- оглушение (пробитый блок, пропущенный удар) и короткое восстановление
    def _st_stun(self, world, direction):
        self._brake(0.15)
        self.state_t -= 1
        if self.state_t <= 0:
            self._set("move")

    _st_recover = _st_stun

    # --- удары
    def _start_attack(self, world, kind):
        w = self.weapon
        cost = {"heavy": HEAVY_COST, "plunge": PLUNGE_COST}.get(kind, w.stamina)
        self.spend(cost)
        self.attack_kind = kind
        self.hit_ids.clear()
        if kind != "light" or self.combo == 0:
            self.queued = 0
        if kind == "plunge":
            self._set("plunge")
            self.vy = 4.4
            audio.sfx(audio.SWING)
            return
        dur = w.swing
        if kind == "heavy":
            dur = int(w.swing * 1.5) + 6
            audio.sfx(audio.HEAVY)
        else:
            if kind == "light" and self.combo == COMBO_MAX - 1:
                dur = int(dur * 1.15)
            audio.sfx(audio.SWING)
        self.attack_dur = self.attack_t = dur
        self._set("attack")

    def attack_progress(self):
        return 1 - self.attack_t / max(1, self.attack_dur)

    def attack_active(self):
        if self.state != "attack":
            return False
        lo, hi = (0.35, 0.8) if self.attack_kind == "heavy" else (0.2, 0.75)
        return lo <= self.attack_progress() <= hi

    def attack_damage(self):
        atk = self.inv.attack
        if self.attack_kind == "heavy":
            return atk * 2
        if self.attack_kind == "plunge":
            return math.ceil(atk * 1.5)
        if self.attack_kind == "light" and self.combo == COMBO_MAX - 1:
            return math.ceil(atk * 1.3)
        return atk

    def attack_box(self):
        reach = self.weapon.reach + (4 if self.attack_kind == "heavy" else 0)
        hx = self.x + self.w if self.facing > 0 else self.x - reach
        return hx, self.y - 2, reach, self.h

    def _st_attack(self, world, direction):
        on_ground_attack = self.attack_kind in ("light", "heavy") and self.on_ground
        if on_ground_attack:
            self._walk(direction, 0.45 if self.attack_kind == "light" else 0.2, turn=False)
        else:
            self._walk(direction, 1.0, turn=False)
        if self.attack_active():
            self._hit_box(world, *self.attack_box())
        if self.attack_kind == "light" and self.buf_attack:
            self.buf_attack = 0
            self.queued = min(COMBO_MAX - 1 - self.combo, self.queued + 1)
        self.attack_t -= 1
        if self.attack_t > 0:
            return
        if self.attack_kind == "light" and self.queued > 0 and self.combo < COMBO_MAX - 1 and self.on_ground:
            if self.can_act():
                self.queued -= 1
                self.combo += 1
                if direction:
                    self.facing = direction
                self._start_attack(world, "light")
                return
        if self.attack_kind == "light" and controls.held("attack") and self.on_ground:
            self.charge = 0
            self._set("charge")
            return
        self.combo = 0
        self._set("move")

    def _st_charge(self, world, direction):
        self._walk(direction, 0.3, turn=False)
        self.charge += 1
        if self.charge == CHARGE_TIME:
            audio.sfx(audio.CHARGED)
            world.sparks(self.cx + self.facing * 6, self.y + 4, 4)
        if self._take("roll") and self.can_act():
            self._start_roll(world, direction)
        elif not controls.held("attack"):
            if self.charge >= CHARGE_TIME and self.can_act():
                self.combo = 0
                self._start_attack(world, "heavy")
                world.shake(2)
            else:
                self._set("move")

    def _st_plunge(self, world, direction):
        self._brake(0.1)
        self.vy = 4.4
        if self.on_ground:
            world.dust(self.cx, self.y + self.h, 6)
            world.shake(2)
            self._set("recover", 12)

    def _plunge_contact(self, world):
        if self.state != "plunge":
            return
        if self._hit_box(world, self.x - 3, self.y + self.h - 2, self.w + 6, 10):
            self.vy = -3.4
            self._set("move")

    def _hit_box(self, world, hx, hy, hw, hh):
        """Бьёт врагов и стрелы в прямоугольнике. Возвращает True, если по кому-то попал."""
        hit_any = False
        for enemy in world.enemies:
            if id(enemy) in self.hit_ids or enemy.dead or not rect_overlap(hx, hy, hw, hh, enemy):
                continue
            self.hit_ids.add(id(enemy))
            hit_any = True
            result = enemy.take_hit(self.attack_damage(), self.facing, world,
                                    heavy=self.attack_kind == "heavy",
                                    plunge=self.attack_kind == "plunge")
            if result == "blocked":
                audio.sfx(audio.BLOCK)
                self.vx = -self.facing * 1.6
                self.spend(10)
                world.freeze(3)
        for arrow in world.projectiles:
            if arrow.deflectable and rect_overlap(hx, hy, hw, hh, arrow):
                arrow.deflect(world)
                hit_any = True
        return hit_any

    # ------------------------------------------------------------ урон
    def take_damage(self, dmg, from_x, world, parryable=True, source=None, unblockable=False):
        """Возвращает "miss", "parry", "blocked" или "hit"."""
        if self.dead or self.invuln > 0 or self.rolling_invuln():
            return "miss"
        if self.shield_t > 0 and not unblockable:
            audio.sfx(audio.BLOCK)
            world.sparks(self.cx, self.cy, 6)
            if source is not None and hasattr(source, "on_blocked"):
                source.on_blocked(world, self)
            return "blocked"
        front = (from_x - self.cx) * self.facing >= 0
        if self.state == "block" and front and not unblockable:
            if parryable and self.block_t <= PARRY_WINDOW:
                self._parry(world, source)
                return "parry"
            shield = self.inv.equipped("shield")
            cost = max(8, dmg * 9 - (shield.defense * 4 if shield else 0))
            if not shield:
                cost = int(cost * 1.3)
            if self.stamina >= cost:
                self.spend(cost)
                audio.sfx(audio.BLOCK)
                world.sparks(self.cx + self.facing * 7, self.y + 6, 6)
                world.freeze(3)
                self.vx = -self.facing * 1.2
                if source is not None and hasattr(source, "on_blocked"):
                    source.on_blocked(world, self)
                if shield:
                    return "blocked"
                dmg = math.ceil(dmg * 0.5)  # без щита часть удара проходит
            else:
                self.stamina = 0
                self.stamina_wait = EXHAUST_DELAY
                self.stamina_flash = 30
                audio.sfx(audio.GUARD_BREAK)
                world.float_text(self.cx, self.y - 12, "ЩИТ ПРОБИТ", 8)
                dmg = math.ceil(dmg * 0.5)
                self._set("stun", 45)
                self._apply_damage(dmg, from_x, world, knock=0.8)
                return "hit"
        self._apply_damage(dmg, from_x, world)
        if not self.dead:
            self._set("stun", 14)
        return "hit"

    def _apply_damage(self, dmg, from_x, world, knock=1.0):
        defense = self.inv.defense
        actual = max(1, math.ceil(dmg * 6 / (6 + defense)))
        self.hp -= actual
        self.invuln = self.INVULN
        self.flash = 8
        self.combo = 0
        side = 1 if self.cx >= from_x else -1
        self.vx = side * 2.2 * knock
        self.vy = -2.2 * knock
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
        self._apply_damage(2, self.cx, world)
        if not self.dead:
            self.x, self.y = self.safe_pos
            self.vx = self.vy = 0
            self._set("move")
            self.invuln = max(self.invuln, was_invuln)

    def heal(self, amount):
        before = self.hp
        self.hp = min(self.inv.max_hp, self.hp + amount)
        return self.hp - before

    # ------------------------------------------------------------ отрисовка
    def frame(self):
        st = self.state
        if self.dead:
            return sprites.anim_at("death", self.dead_t / 40)
        if st == "roll":
            return sprites.anim_at("roll", 1 - self.state_t / self.ROLL_TIME)
        if st == "attack":
            p = self.attack_progress()
            if self.attack_kind == "heavy":
                return sprites.anim_at("heavy", p, start=1)
            name = "attack2" if self.attack_kind == "light" and self.combo == 1 else "attack"
            return sprites.anim_at(name, p)
        if st == "charge":
            return sprites.anim("heavy", 0)
        if st == "plunge":
            return sprites.anim("plunge")
        if st == "cast":
            return sprites.anim("cast", self.anim_t // 6)
        if st == "block":
            return sprites.anim("block")
        if st == "stun" or self.flash:
            return sprites.anim("hurt")
        if not self.on_ground:
            return sprites.anim("jump" if self.vy < 0 else "fall")
        if abs(self.vx) > 0.2 and st == "move":
            return sprites.anim("run", self.anim_t // 5)
        return sprites.anim("idle", pyxel.frame_count // 15)

    def hand(self):
        return sprites.anchor(self.frame(), "hand", self.cx, self.y + self.h, self.facing)

    def draw(self):
        if self.invuln > 0 and not self.dead and (self.invuln // 3) % 2:
            return
        weapon = self.weapon if self.weapon is not FIST else None
        shield = self.inv.equipped("shield")
        frame = self.frame()
        charged = self.state == "charge" and self.charge >= CHARGE_TIME and (self.anim_t // 3) % 2
        draw_humanoid(
            self.look, frame, self.cx, self.y + self.h, self.facing,
            weapon=None if self.state in ("cast", "roll") or self.dead else weapon,
            shield=shield if self.state != "roll" else None,
            shield_front=self.state == "block",
            flash=self.flash > 0,
            weapon_tint={"6": "a", "f": "a"} if charged else None,
        )
        if self.attack_active() and weapon:
            self._draw_slash(frame)
        if self.state == "stun" and self.state_t > 14:
            draw_stun_stars(self.cx, self.y - 7)
        if self.state == "cast":
            spell = spells.SPELLS[self.cast_spell]
            hx, hy = sprites.anchor(frame, "hand", self.cx, self.y + self.h, self.facing)
            r = 1 + (self.anim_t // 3) % 3
            pyxel.circ(hx + self.facing * 2, hy, r, spell.color)
            pyxel.pset(hx + self.facing * 2, hy, 15)
        spells.draw_shield_aura(self)

    def _draw_slash(self, frame):
        """Дуга-след за клинком."""
        angle = sprites.info(frame)["weapon"]
        if angle is None:
            return
        heavy = self.attack_kind == "heavy"
        hx, hy = sprites.anchor(frame, "hand", self.cx, self.y + self.h, self.facing)
        r = 14 + (4 if heavy else 0)
        back = 1 if self.attack_kind == "light" and self.combo == 1 else -1
        for i in range(12 if heavy else 8):
            a = math.radians(angle + back * i * 8)
            px = hx + math.sin(a) * r * self.facing
            py = hy - math.cos(a) * r
            col = (10 if i < 5 else 9) if heavy else (15 if i < 3 else 7)
            pyxel.pset(px, py, col)
            if heavy:
                pyxel.pset(px, py + 1, col)
