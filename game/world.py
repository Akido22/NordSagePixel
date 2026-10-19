"""Игровой мир одной локации: уровень, герой, враги, объекты, камера, эффекты и сохранение."""

import os
import random

import pyxel

from . import audio, controls, font, items, save
from .config import LEVELS_DIR, SCREEN_W, TILE
from .enemies import Archer, Draugr, Dummy, ShieldDraugr, Wolf
from .entities import Chest, Decor, EdgeExit, Gate, Npc, Pickup, Runestone, Sign, Stela, overlap
from .player import Player
from .level import Level
from .props import Prop
from .state import GameState

INTERACT_DIST = 14


class World:
    def __init__(self, state=None, level_name=None, spawn=None):
        self.state = state or GameState()
        st = self.state
        name = level_name or st.level
        self.level = Level(os.path.join(LEVELS_DIR, f"{name}.txt"), name)
        st.level = name
        self.particles = []
        self.texts = []
        self.toasts = []
        self.shake_t = 0
        self.hitstop = 0  # «стоп-кадр» при сильных попаданиях
        self.projectiles = []
        self.cam_x = 0.0
        self.finished = False
        self.exit_to = None  # (локация, точка появления) — запрошенный переход
        self.near = None
        self.talk_npc = None

        self.enemies = []
        self.pickups = []
        self.chests = []
        self.save_points = []
        self.signs = []
        self.gates = []
        self.edge_exits = []
        self.decor = []
        self.props = [Prop(kind, x, y, w) for kind, x, y, w in self.level.props]
        self.npcs = [Npc(x, y, npc_id) for x, y, npc_id in self.level.npcs]
        start = (0, 0)
        for ch, tx, ty in self.level.objects:
            px, py = tx * TILE, (ty + 1) * TILE
            if ch == "P":
                start = (px, py - Player.h)
            elif ch == "W":
                self.enemies.append(Wolf(px - 3, py - Wolf.h))
            elif ch == "D":
                self.enemies.append(Draugr(px, py - Draugr.h))
            elif ch == "K":
                self.enemies.append(ShieldDraugr(px, py - ShieldDraugr.h))
            elif ch == "A":
                self.enemies.append(Archer(px, py - Archer.h))
            elif ch == "U":
                self.enemies.append(Dummy(px - 1, py - Dummy.h))
            elif ch in "oh":
                uid = f"{ch}{tx},{ty}"
                if self._key(uid) not in st.collected:
                    kind = "coin" if ch == "o" else "honey"
                    self.pickups.append(Pickup(px, py - 8, kind, uid=uid, floating=True))
            elif ch == "C":
                chest = Chest(tx, ty, self.level.chests.get((tx, ty), []))
                if self._key(chest.uid) in st.chests:
                    chest.loot = list(st.chests[self._key(chest.uid)])
                    chest.opened = not chest.loot
                self.chests.append(chest)
            elif ch in "RT":
                point = Runestone(tx, ty) if ch == "R" else Stela(tx, ty)
                point.active = self._key(point.uid) == st.save_point
                self.save_points.append(point)
            elif ch == "Y":
                self.signs.append(Sign(tx, ty, self.level.signs.get((tx, ty), "...")))
            elif ch == "E":
                target, spawn_name, style = self.level.exits.get((tx, ty), ("end", None, "forest"))
                self.gates.append(Gate(tx, ty, target, spawn_name, style))
            elif ch == "X":
                target, spawn_name, _ = self.level.exits.get((tx, ty), ("end", None, ""))
                self.edge_exits.append(EdgeExit(tx, ty, target, spawn_name))
            elif ch in "BIF":
                self.decor.append(Decor(ch, tx, ty))

        # Где появиться герою: точное место из сохранения, именованная точка или старт.
        if st.pos is not None:
            pos = st.pos
        elif spawn or st.spawn:
            sx, sy = self.level.spawns.get(spawn or st.spawn, (start[0] // TILE, (start[1] + Player.h) // TILE - 1))
            pos = (sx * TILE, (sy + 1) * TILE - Player.h)
        else:
            pos = start
        st.pos = None
        self.player = Player(*pos, st.inventory)
        self.player.hp = max(1, min(st.inventory.max_hp, st.hp))
        self.player.safe_pos = (self.player.x, self.player.y)
        self.cam_x = self._target_cam()
        self.title_t = 180  # показ названия локации

    def _key(self, uid):
        return GameState.key(self.level.name, uid)

    # ------------------------------------------------------------ сохранение
    def sync_state(self):
        """Переносит изменчивое состояние локации в общее состояние похода."""
        st = self.state
        st.hp = self.player.hp
        for chest in self.chests:
            if chest.loot != self.level.chests.get(tuple(int(v) for v in chest.uid.split(",")), []):
                st.chests[self._key(chest.uid)] = list(chest.loot)

    def save_game(self):
        self.sync_state()
        ok = save.write(self.state.to_save(self.level.name, self.player.safe_pos))
        self.toast("Путь сохранён" if ok else "Не удалось сохранить!", 10 if ok else 8)
        if ok:
            audio.sfx(audio.SAVE)
        return ok

    # ------------------------------------------------------------ события
    def toast(self, text, col=7):
        self.toasts.append([text, col, 150])
        self.toasts = self.toasts[-3:]

    def float_text(self, x, y, text, col):
        self.texts.append([x, y, text, col, 40])

    def shake(self, amount):
        self.shake_t = max(self.shake_t, amount)

    def freeze(self, frames):
        self.hitstop = max(self.hitstop, frames)

    def dust(self, x, y, n=5):
        for _ in range(n):
            self.particles.append([x, y, random.uniform(-0.8, 0.8), random.uniform(-0.6, -0.1),
                                   random.randint(10, 18), 7, 0.05])

    def sparks(self, x, y, n=6):
        for _ in range(n):
            self.particles.append([x, y, random.uniform(-1.6, 1.6), random.uniform(-1.8, 0.2),
                                   random.randint(8, 16), random.choice((10, 15, 9)), 0.05])

    def smoke(self, x, y, n=12):
        for _ in range(n):
            self.particles.append([x + random.uniform(-4, 4), y + random.uniform(-6, 4),
                                   random.uniform(-0.4, 0.4), random.uniform(-0.9, -0.2),
                                   random.randint(18, 34), random.choice((5, 6, 13)), 0.01])

    def puff(self, x, y):
        """Дымок из трубы: медленно поднимается и сносится ветром."""
        self.particles.append([x + random.uniform(-1, 1), y, random.uniform(0.05, 0.25),
                               random.uniform(-0.5, -0.3), random.randint(40, 70), random.choice((5, 6)), 0.0])

    def on_enemy_killed(self, enemy):
        self.smoke(enemy.cx, enemy.cy)
        self.shake(2)
        for _ in range(random.randint(*enemy.silver)):
            coin = Pickup(enemy.cx - 4, enemy.y, "coin")
            coin.vx = random.uniform(-1.2, 1.2)
            coin.vy = random.uniform(-2.8, -1.6)
            self.pickups.append(coin)
        if isinstance(enemy, Draugr) and random.random() < 0.5:
            drop = Pickup(enemy.cx - 4, enemy.y, "bread")
            drop.vy = -2.5
            self.pickups.append(drop)

    def collect(self, pickup):
        inv = self.player.inv
        if pickup.kind == "coin":
            inv.silver += 1
            audio.sfx(audio.COIN)
        else:
            if not inv.add(pickup.kind):
                if pickup.age % 120 == 21:
                    self.toast("Сума полна!", 8)
                return
            self.toast("Получено: " + items.get(pickup.kind).name, 10)
            audio.sfx(audio.COIN)
        pickup.taken = True
        if pickup.uid:
            self.state.collected.add(self._key(pickup.uid))
        self.sparks(pickup.cx, pickup.cy, 4)

    def use_heal_item(self):
        p = self.player
        inv = p.inv
        if p.hp >= inv.max_hp:
            self.toast("Ты и так полон сил", 6)
            audio.sfx(audio.DENY)
            return
        idx = inv.first_consumable()
        if idx is None:
            self.toast("В суме нет припасов", 6)
            audio.sfx(audio.DENY)
            return
        item = inv.item_at(idx)
        healed = p.heal(item.heal)
        inv.remove_at(idx)
        self.float_text(p.cx, p.y - 4, f"+{healed}", 11)
        self.toast(item.name + ": +" + str(healed), 11)
        audio.sfx(audio.HEAL)

    def _interact(self, obj):
        p = self.player
        if isinstance(obj, Chest) and not obj.opened:
            audio.sfx(audio.CHEST)
            left = []
            for item_id in obj.loot:
                if p.inv.add(item_id):
                    self.toast("Получено: " + items.get(item_id).name, 10)
                else:
                    left.append(item_id)
            obj.loot = left
            obj.opened = not left
            if left:
                self.toast("Сума полна! Освободи место", 8)
            self.sparks(obj.x + 8, obj.y + 2, 10)
        elif isinstance(obj, (Runestone, Stela)):
            for point in self.save_points:
                point.active = point is obj
            self.state.save_point = self._key(obj.uid)
            p.hp = p.inv.max_hp
            self.float_text(p.cx, p.y - 4, "РУНЫ" if isinstance(obj, Runestone) else "ПРЕДКИ", 10)
            self.save_game()
        elif isinstance(obj, Npc):
            obj.talk()
            self.talk_npc = obj if obj.talking else None
            audio.sfx(audio.MOVE)
        elif isinstance(obj, Gate):
            self._leave(obj.target, obj.spawn)

    def _leave(self, target, spawn):
        if target == "end":
            self.finished = True
        else:
            self.sync_state()
            self.exit_to = (target, spawn)

    # ------------------------------------------------------------ цикл
    def update(self):
        self.player.poll_input()
        if self.hitstop > 0:
            self.hitstop -= 1
            return
        p = self.player
        p.update(self)
        for e in self.enemies:
            e.update(self)
        self.enemies = [e for e in self.enemies if not e.dead]
        for arrow in self.projectiles:
            arrow.update(self)
        self.projectiles = [a for a in self.projectiles if not a.dead]
        for pk in self.pickups:
            pk.update(self)
        self.pickups = [pk for pk in self.pickups if not pk.taken]
        for prop in self.props:
            prop.update(self)
        for npc in self.npcs:
            npc.update(self)
        if self.talk_npc is not None and not self.talk_npc.talking:
            self.talk_npc = None
        if self.title_t > 0:
            self.title_t -= 1

        # Ближайший объект для взаимодействия.
        self.near = None
        best = INTERACT_DIST
        if not p.dead:
            for obj in self.chests + self.save_points + self.signs + self.gates + self.npcs:
                d = abs((obj.x + obj.w / 2) - p.cx)
                if d < best + obj.w / 2 and abs((obj.y + obj.h) - (p.y + p.h)) < 12:
                    self.near = obj
                    best = d
            if self.near is not None and controls.pressed("up"):
                self._interact(self.near)
            if controls.pressed("heal"):
                self.use_heal_item()
            for ex in self.edge_exits:
                if overlap(p, ex) and self.exit_to is None:
                    self._leave(ex.target, ex.spawn)

        for part in self.particles:
            part[0] += part[2]
            part[1] += part[3]
            part[3] += part[6]
            part[4] -= 1
        self.particles = [pt for pt in self.particles if pt[4] > 0]
        for t in self.texts:
            t[1] -= 0.4
            t[4] -= 1
        self.texts = [t for t in self.texts if t[4] > 0]
        for t in self.toasts:
            t[2] -= 1
        self.toasts = [t for t in self.toasts if t[2] > 0]
        if self.shake_t > 0:
            self.shake_t -= 1

        target = self._target_cam()
        self.cam_x += (target - self.cam_x) * 0.12

    def _target_cam(self):
        p = self.player
        look = p.facing * 24
        return max(0, min(self.level.pixel_w - SCREEN_W, p.cx - SCREEN_W / 2 + look))

    # ------------------------------------------------------------ отрисовка
    def draw(self):
        cam = int(self.cam_x)
        if self.shake_t > 0:
            cam += random.randint(-1, 1) * min(2, self.shake_t)
        self.level.background.draw(cam)
        pyxel.camera(cam, 0)
        for prop in self.props:
            if prop.x + prop.w + 48 > cam and prop.x - 48 < cam + SCREEN_W:
                prop.draw()
        for d in self.decor:
            if d.kind != "F":
                d.draw()
        self.level.draw_tiles(cam)
        for obj in self.gates + self.edge_exits + self.signs + self.save_points + self.chests:
            obj.draw()
        for d in self.decor:
            if d.kind == "F":
                d.draw()
        for npc in self.npcs:
            npc.draw()
        for pk in self.pickups:
            pk.draw()
        for e in self.enemies:
            if -24 < e.x - cam < SCREEN_W + 24:
                e.draw()
        self.player.draw()
        for arrow in self.projectiles:
            arrow.draw()
        for x, y, _, _, _, col, _ in self.particles:
            pyxel.pset(x, y, col)
        for x, y, text, col, _ in self.texts:
            font.text_center(x, y, text, col, shadow=1)
        if self.near is not None and not self.player.dead:
            hint = self.near.hint()
            if hint:
                bob = (pyxel.frame_count // 15) % 2
                label = font.ARROW_UP + " " + hint
                font.text_center(self.near.x + self.near.w / 2, self.near.y - 11 - bob, label, 15, shadow=1)
        pyxel.camera()
