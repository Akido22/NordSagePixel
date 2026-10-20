"""Сцены: главное меню, игра, пауза, сума и снаряжение, смерть, финал."""

import pyxel

from . import audio, controls, font, gfx, items, save, ui
from .config import GAME_TITLE, SCREEN_H, SCREEN_W
from .entities import Sign, draw_humanoid
from .inventory import BAG_COLS, BAG_ROWS, BAG_SIZE, xp_needed
from .level import Background
from .menus import NpcMenuScene, RestScene
from .spells import SPELLS
from .state import GameState
from .world import World

FADE = 18


def new_game_world():
    return World(GameState())


def load_world():
    data = save.load()
    return World(GameState.from_save(data)) if data else None


class Scene:
    def __init__(self, app):
        self.app = app

    def update(self):
        pass

    def draw(self):
        pass


# ===================================================================== главное меню
class TitleScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.bg = Background("town")
        self.cam = 0.0
        self.has_save = save.exists()
        self.menu = ui.Menu([
            ("Продолжить", self.has_save),
            ("Новая игра", True),
            ("Управление", True),
            ("Выход", True),
        ])
        audio.music_start(audio.TOWN)

    def update(self):
        self.cam += 0.3
        choice = self.menu.update()
        if choice == 0:
            world = load_world()
            if world:
                self.app.set_scene(PlayScene(self.app, world))
        elif choice == 1:
            self.app.set_scene(PlayScene(self.app, new_game_world()))
        elif choice == 2:
            self.app.set_scene(ControlsScene(self.app, self))
        elif choice == 3:
            pyxel.quit()

    def draw(self):
        self.bg.draw(self.cam)
        # Земля и силуэт городища на переднем плане.
        pyxel.rect(0, 170, SCREEN_W, 22, 1)
        for i in range(0, SCREEN_W, 6):
            pyxel.rect(i, 160 + (i * 7) % 5, 4, 12, 2)
            pyxel.tri(i, 160 + (i * 7) % 5, i + 2, 156 + (i * 7) % 5, i + 4, 160 + (i * 7) % 5, 2)
        ui.ornament_band(28, 30, SCREEN_W - 56)
        font.text_big(SCREEN_W // 2, 40, GAME_TITLE.upper(), 10, scale=2, shadow=8)
        font.text_center(SCREEN_W // 2, 62, "Глава I. Велеград", 7, shadow=1)
        ui.ornament_band(28, 76, SCREEN_W - 56)
        ui.panel(78, 88, 100, 64)
        self.menu.draw(SCREEN_W // 2, 96)
        font.text_center(SCREEN_W // 2, 178, "M - музыка   ALT+ENTER - во весь экран", 5)


# ===================================================================== управление
CONTROLS_TEXT = [
    ("Идти", f"{font.ARROW_LEFT} {font.ARROW_RIGHT}  /  A D"),
    ("Прыжок", "ПРОБЕЛ / Z / K"),
    ("Удар (держи - сильный)", "X / J"),
    ("Удар сверху в прыжке", f"{font.ARROW_DOWN} + удар"),
    ("Щит, парирование", "C / L"),
    ("Перекат", "V / SHIFT"),
    ("Чары руны", "F / U"),
    ("Сменить руну", "E / O"),
    ("Спрыгнуть с доски", f"{font.ARROW_DOWN} + прыжок"),
    ("Говорить, торговать, открыть", f"{font.ARROW_UP} / W"),
    ("Подлечиться", "Q / H"),
    ("Сума и снаряжение", "I / TAB"),
    ("Пауза", "ESC / P"),
    ("Музыка вкл/выкл", "M"),
]


class ControlsScene(Scene):
    def __init__(self, app, back_scene):
        super().__init__(app)
        self.back_scene = back_scene

    def update(self):
        if controls.pressed("back") or controls.pressed("confirm"):
            audio.sfx(audio.SELECT)
            self.app.set_scene(self.back_scene)

    def draw(self):
        self.back_scene.draw()
        ui.dim(0.7)
        ui.panel(12, 14, 232, 170)
        ui.title_plate(SCREEN_W // 2, 7, "УПРАВЛЕНИЕ")
        for i, (action, keys) in enumerate(CONTROLS_TEXT):
            y = 27 + i * 10
            font.text(22, y, action, 7, shadow=0)
            font.text(150, y, keys, 10, shadow=0)
        font.text_center(SCREEN_W // 2, 172, "Геймпад тоже работает", 5)


# ===================================================================== игра
class PlayScene(Scene):
    def __init__(self, app, world):
        super().__init__(app)
        self.world = world
        self.dead_t = 0
        self.fade = FADE  # >0 — проявление после входа в локацию
        self.fade_out = 0  # >0 — затемнение перед переходом
        audio.music_start(world.level.music)

    def update(self):
        if self.fade > 0:
            self.fade -= 1
        if self.fade_out > 0:
            self.fade_out -= 1
            if self.fade_out == 0:
                target, spawn = self.world.exit_to
                self.world = World(self.world.state, target, spawn)
                self.fade = FADE
                audio.music_start(self.world.level.music)
            return
        w = self.world
        if w.exit_to is not None:
            self.fade_out = FADE
            return
        if controls.pressed("pause"):
            audio.sfx(audio.SELECT)
            self.app.set_scene(PauseScene(self.app, self))
            return
        if controls.pressed("inventory") and not w.player.dead:
            audio.sfx(audio.SELECT)
            self.app.set_scene(InventoryScene(self.app, self))
            return
        w.update()
        if w.ui_request is not None:
            kind, target = w.ui_request
            w.ui_request = None
            scene = RestScene if kind == "rest" else NpcMenuScene
            self.app.set_scene(scene(self.app, self, target))
            return
        if w.player.dead:
            if self.dead_t == 0:
                w.on_player_died()
            self.dead_t += 1
            if self.dead_t > 90:
                self.app.set_scene(DeathScene(self.app, self))
        if w.finished:
            audio.sfx(audio.SAVE)
            self.app.set_scene(VictoryScene(self.app, self))

    def draw(self):
        self.world.draw()
        self.draw_hud()
        darkness = self.fade / FADE if self.fade else (1 - self.fade_out / FADE if self.fade_out else 0)
        if darkness > 0:
            ui.dim(min(1.0, darkness), 0)

    def draw_hud(self):
        w = self.world
        p = w.player
        inv = p.inv
        # Здоровье и выносливость.
        pyxel.rect(2, 2, 122, 32, 0)
        pyxel.rectb(2, 2, 122, 32, 2)
        need = xp_needed(inv.level)
        pyxel.line(3, 32, 3 + int(118 * inv.xp / need), 32, 10)
        lvl_col = 10 if inv.points and (pyxel.frame_count // 15) % 2 else 6
        font.text(96, 23, f"УР.{inv.level}" + ("+" if inv.points else ""), lvl_col)
        gfx.icon("heart", 5, 3)
        ui.bar(15, 4, 60, 6, p.hp, inv.max_hp, 8)
        font.text(79, 3, f"{p.hp}/{inv.max_hp}", 7)
        stamina_col = 8 if p.stamina_flash and (p.stamina_flash // 3) % 2 else 11
        ui.bar(15, 11, 60, 4, p.stamina, p.stamina_max, stamina_col, shine=False)
        ui.bar(15, 16, 60, 4, p.mana, inv.max_mana, 12, shine=False)
        font.text(79, 14, str(int(p.mana)), 12)
        gfx.icon("coin", 5, 22)
        font.text(15, 23, str(inv.silver), 7)
        idx = inv.first_consumable()
        if idx is not None:
            item = inv.item_at(idx)
            total = sum(inv.count_at(i) for i in range(len(inv.bag)) if inv.item_at(i) and inv.item_at(i).heal)
            gfx.icon(item.icon, 52, 22, item.tint)
            font.text(62, 23, f"x{total} Q", 7)
        # Выбранная руна.
        rune = inv.spell
        if rune is not None:
            ritem = items.get(rune)
            cost = SPELLS[rune].cost
            ready = p.mana >= cost
            pyxel.rect(126, 2, 22, 32, 0)
            pyxel.rectb(126, 2, 22, 32, 12 if ready else 2)
            gfx.icon(ritem.icon, 129, 5, ritem.tint, scale=2)
            font.text(130, 24, "F", 12 if ready else 5)
            font.text(137, 24, str(cost), 12 if ready else 5)
        # Сообщения.
        banner_on = 0 < w.title_t < 170
        for i, (text, col, life) in enumerate(w.toasts):
            if life < 20 and (life // 2) % 2:
                continue
            tw = font.text_width(text)
            y = (76 if banner_on else 38) + i * 11
            pyxel.dither(0.7)
            pyxel.rect(SCREEN_W // 2 - tw // 2 - 4, y - 2, tw + 8, 11, 0)
            pyxel.dither(1.0)
            font.text_center(SCREEN_W // 2, y, text, col)
        # Название локации при входе.
        if w.title_t > 0 and w.title_t < 170:
            if w.title_t > 30 or (w.title_t // 3) % 2:
                ui.backdrop(36, 34, line=10)
                title, subtitle = w.banner or (w.level.title, w.level.subtitle)
                font.text_big(SCREEN_W // 2, 41, title.upper(), 10, scale=2, shadow=8)
                if subtitle:
                    font.text_center(SCREEN_W // 2, 59, subtitle, 7)
        # Полоса здоровья босса.
        boss = w.boss
        if boss is not None and boss.awake and not boss.dead and boss.state != "rise":
            ui.panel(26, SCREEN_H - 24, SCREEN_W - 52, 20, fill=0, border=10, accent=8)
            font.text_center(SCREEN_W // 2, SCREEN_H - 20, boss.name, 10)
            col = 8 if boss.phase == 1 or (pyxel.frame_count // 8) % 2 else 9
            ui.bar(36, SCREEN_H - 11, SCREEN_W - 72, 5, boss.hp, boss.max_hp, col)
        # Разговор.
        npc = w.talk_npc
        if npc is not None:
            lines = font.wrap(npc.data.lines[npc.line], 200)
            h = 26 + len(lines) * font.LINE_H
            y = 28
            ui.panel(20, y, 216, h, fill=1, border=10, accent=8)
            font.text(30, y + 7, npc.data.name, 10, shadow=0)
            for i, line in enumerate(lines):
                font.text(30, y + 18 + i * font.LINE_H, line, 7, shadow=0)
            more = npc.line + 1 < len(npc.data.lines)
            tag = font.ARROW_UP + (" далее" if more else " конец")
            font.text(226 - font.text_width(tag), y + 7, tag, 5)
        # Табличка.
        if isinstance(w.near, Sign):
            lines = font.wrap(w.near.text, 200)
            h = 14 + len(lines) * font.LINE_H
            y = 64
            ui.panel(20, y, 216, h, fill=2, border=4, accent=10)
            for i, line in enumerate(lines):
                font.text(30, y + 7 + i * font.LINE_H, line, 7, shadow=1)


# ===================================================================== пауза
class PauseScene(Scene):
    def __init__(self, app, play):
        super().__init__(app)
        self.play = play
        self.confirm_exit = False
        self.menu = ui.Menu([
            ("Продолжить", True),
            ("Сума и снаряжение", True),
            ("Сохранить игру", True),
            ("Управление", True),
            ("В главное меню", True),
        ])
        self.confirm = ui.Menu([("Да, выйти", True), ("Нет", True)], index=1)

    def update(self):
        if self.confirm_exit:
            if controls.pressed("back"):
                self.confirm_exit = False
                return
            choice = self.confirm.update()
            if choice == 0:
                self.app.set_scene(TitleScene(self.app))
            elif choice == 1:
                self.confirm_exit = False
            return
        if controls.pressed("back") or controls.pressed("pause"):
            audio.sfx(audio.SELECT)
            self.app.set_scene(self.play)
            return
        choice = self.menu.update()
        if choice == 0:
            self.app.set_scene(self.play)
        elif choice == 1:
            self.app.set_scene(InventoryScene(self.app, self.play, return_to=self))
        elif choice == 2:
            self.play.world.save_game()
            self.app.set_scene(self.play)
        elif choice == 3:
            self.app.set_scene(ControlsScene(self.app, self))
        elif choice == 4:
            self.confirm_exit = True

    def draw(self):
        self.play.draw()
        ui.dim(0.6)
        ui.panel(60, 44, 136, 96)
        ui.title_plate(SCREEN_W // 2, 37, "ПРИВАЛ")
        if self.confirm_exit:
            font.text_center(SCREEN_W // 2, 62, "Выйти в главное меню?", 7)
            font.text_center(SCREEN_W // 2, 74, "Несохранённый путь", 6)
            font.text_center(SCREEN_W // 2, 84, "будет потерян.", 6)
            self.confirm.draw(SCREEN_W // 2, 104)
        else:
            self.menu.draw(SCREEN_W // 2, 60)


# ===================================================================== сума и снаряжение
SLOT_SIZE = 19
BAG_X, BAG_Y = 132, 30
# Колонки снаряжения вокруг фигуры героя: слева шлем/оружие/доспех, справа щит/оберег.
EQUIP_COLUMNS = [["helmet", "weapon", "armor"], ["shield", "amulet"]]
EQUIP_POS = {
    "helmet": (12, 30), "weapon": (12, 54), "armor": (12, 78),
    "shield": (98, 30), "amulet": (98, 54),
}


class InventoryScene(Scene):
    def __init__(self, app, play, return_to=None):
        super().__init__(app)
        self.play = play
        self.return_to = return_to or play
        self.col = 2  # 0..1 — снаряжение, 2..7 — сума
        self.row = 0
        self.confirm_drop = False
        self.msg = None
        self.msg_t = 0

    @property
    def player(self):
        return self.play.world.player

    @property
    def inv(self):
        return self.player.inv

    def _column_len(self, col):
        return len(EQUIP_COLUMNS[col]) if col < 2 else BAG_ROWS

    def _selected(self):
        """(вид, ключ): ("slot", имя_слота) или ("bag", индекс)."""
        if self.col < 2:
            return "slot", EQUIP_COLUMNS[self.col][self.row]
        return "bag", self.row * BAG_COLS + (self.col - 2)

    def _say(self, text):
        self.msg = text
        self.msg_t = 120

    def update(self):
        if self.msg_t > 0:
            self.msg_t -= 1
        if self.confirm_drop:
            if controls.pressed("drop"):
                kind, idx = self._selected()
                item = self.inv.item_at(idx)
                self.inv.bag[idx] = None
                self._say("Выброшено: " + item.name)
                audio.sfx(audio.HIT)
                self.confirm_drop = False
            elif controls.pressed("back") or controls.pressed("confirm") or controls.pressed("inventory"):
                self.confirm_drop = False
            return

        if controls.pressed("back") or controls.pressed("inventory"):
            audio.sfx(audio.SELECT)
            self.app.set_scene(self.return_to)
            return
        moved = False
        if controls.pressed("left", repeat=True) and self.col > 0:
            self.col -= 1
            moved = True
        elif controls.pressed("right", repeat=True) and self.col < 7:
            self.col += 1
            moved = True
        elif controls.pressed("up", repeat=True) and self.row > 0:
            self.row -= 1
            moved = True
        elif controls.pressed("down", repeat=True) and self.row < self._column_len(self.col) - 1:
            self.row += 1
            moved = True
        if moved:
            self.row = min(self.row, self._column_len(self.col) - 1)
            audio.sfx(audio.MOVE)

        kind, key = self._selected()
        if controls.pressed("confirm"):
            if kind == "slot":
                if self.inv.equipped(key) is None:
                    audio.sfx(audio.DENY)
                elif self.inv.unequip(key):
                    audio.sfx(audio.SELECT)
                    self.player.rebuild_look()
                else:
                    self._say("Сума полна!")
                    audio.sfx(audio.DENY)
            else:
                item = self.inv.item_at(key)
                if item is None:
                    audio.sfx(audio.DENY)
                elif item.kind == "material":
                    self._say("Это для кузни: отнеси Добрыне")
                    audio.sfx(audio.DENY)
                elif item.kind == "consumable" and item.mana and not item.heal:
                    p = self.player
                    if p.mana >= self.inv.max_mana:
                        self._say("Сила чар и так полна")
                        audio.sfx(audio.DENY)
                    else:
                        p.mana = min(self.inv.max_mana, p.mana + item.mana)
                        self.inv.remove_at(key)
                        self._say(f"{item.name}: +{item.mana} маны")
                        audio.sfx(audio.HEAL)
                elif item.kind == "consumable":
                    if self.player.hp >= self.inv.max_hp:
                        self._say("Ты и так полон сил")
                        audio.sfx(audio.DENY)
                    else:
                        healed = self.player.heal(item.heal)
                        self.inv.remove_at(key)
                        self._say(f"{item.name}: +{healed} жизни")
                        audio.sfx(audio.HEAL)
                else:
                    self.inv.equip_from_bag(key)
                    self.player.rebuild_look()
                    self._say("Надето: " + item.name)
                    audio.sfx(audio.CHEST)
        elif controls.pressed("drop") and kind == "bag" and self.inv.item_at(key):
            self.confirm_drop = True
            audio.sfx(audio.MOVE)

    # ------------------------------------------------------------ отрисовка
    def draw(self):
        self.play.world.draw()
        ui.dim(0.75)
        ui.panel(4, 8, SCREEN_W - 8, SCREEN_H - 12)
        ui.title_plate(SCREEN_W // 2, 2, "СУМА И СНАРЯЖЕНИЕ")
        kind, key = self._selected()
        inv = self.inv
        p = self.player

        # --- фигура героя с надетыми вещами
        pyxel.rect(36, 28, 56, 70, 0)
        pyxel.rectb(36, 28, 56, 70, 2)
        pyxel.dither(0.5)
        pyxel.circ(64, 64, 22, 13)
        pyxel.dither(1.0)
        frame = gfx.F_IDLE[(pyxel.frame_count // 32) % 2]
        draw_humanoid(gfx.HERO_ROW, frame, 56, 50, 1, weapon=inv.equipped("weapon"),
                      shield=inv.equipped("shield"), scale=2)
        for slot, (x, y) in EQUIP_POS.items():
            item = inv.equipped(slot)
            ui.item_box(x, y, SLOT_SIZE, item, selected=(kind == "slot" and key == slot))
            if item is None:
                font.text_center(x + SLOT_SIZE // 2 + 1, y + 6, items.SLOT_NAMES[slot][0], 2)

        # --- показатели
        sy = 102
        font.text(12, sy, "Жизнь", 6)
        ui.bar(52, sy, 50, 7, p.hp, inv.max_hp, 8)
        font.text(106, sy, f"{p.hp}/{inv.max_hp}", 7)
        font.text(12, sy + 11, "Атака", 6)
        font.text(52, sy + 11, str(inv.attack), 10)
        font.text(12, sy + 22, "Защита", 6)
        font.text(52, sy + 22, str(inv.defense), 12)
        gfx.icon("coin", 74, sy + 10)
        font.text(84, sy + 11, str(inv.silver), 7)

        # --- сума
        font.text(BAG_X, BAG_Y - 10, "Сума", 6)
        for i in range(BAG_SIZE):
            x = BAG_X + (i % BAG_COLS) * SLOT_SIZE
            y = BAG_Y + (i // BAG_COLS) * SLOT_SIZE
            ui.item_box(x, y, SLOT_SIZE - 1, inv.item_at(i), inv.count_at(i),
                        selected=(kind == "bag" and key == i))

        # --- выученные руны
        font.text(BAG_X, 112, "Руны", 6)
        if not inv.spells:
            font.text(BAG_X + 30, 112, "пока нет", 5)
        for i, rune in enumerate(inv.spells):
            rx = BAG_X + 30 + i * 14
            ritem = items.get(rune)
            if rune == inv.spell:
                pyxel.rectb(rx - 2, 108, 12, 12, 12)
            gfx.icon(ritem.icon, rx, 110, ritem.tint)
        font.text(SCREEN_W - 12 - font.text_width("(E)"), 112, "(E)", 5)

        # --- описание выбранного
        item = inv.equipped(key) if kind == "slot" else inv.item_at(key)
        dy = 137
        pyxel.line(10, dy - 4, SCREEN_W - 11, dy - 4, 2)
        if item:
            font.text(12, dy, inv.item_name(item), 10, shadow=1)
            label = items.KIND_NAMES.get(item.kind, "")
            font.text(SCREEN_W - 12 - font.text_width(label), dy, label, 5)
            stats = "   ".join(item.stat_lines())
            if item.kind == "weapon" and inv.upgrade_level(item.id):
                stats += f"   Заточка +{inv.upgrade_level(item.id)}"
            font.text(12, dy + 10, stats, 11)
            for i, line in enumerate(font.wrap(item.desc, SCREEN_W - 24)[:2]):
                font.text(12, dy + 20 + i * font.LINE_H, line, 7)
        elif kind == "slot":
            font.text(12, dy, items.SLOT_NAMES[key] + ": пусто", 5)
        else:
            font.text(12, dy, "Пустая ячейка", 5)

        # --- подсказка
        hy = SCREEN_H - 16
        if self.confirm_drop:
            font.text_center(SCREEN_W // 2, hy, "Выбросить? R - да, ESC - нет", 8)
        elif self.msg_t > 0:
            font.text_center(SCREEN_W // 2, hy, self.msg, 10)
        else:
            if kind == "slot":
                action = "снять"
            elif item and item.kind == "consumable":
                action = "съесть"
            elif item and item.kind == "material":
                action = "-"
            else:
                action = "надеть"
            font.text_center(SCREEN_W // 2, hy, f"Z - {action}   R - выбросить   I - закрыть", 5)


# ===================================================================== смерть
class DeathScene(Scene):
    def __init__(self, app, play):
        super().__init__(app)
        self.play = play
        self.t = 0
        self.has_save = save.exists()
        self.menu = ui.Menu([
            ("К месту сохранения", self.has_save),
            ("Начать сначала", True),
            ("В главное меню", True),
        ])

    def update(self):
        self.t += 1
        if self.t < 30:
            return
        choice = self.menu.update()
        if choice == 0:
            world = load_world()
            if world:
                self.app.set_scene(PlayScene(self.app, world))
        elif choice == 1:
            self.app.set_scene(PlayScene(self.app, new_game_world()))
        elif choice == 2:
            self.app.set_scene(TitleScene(self.app))

    def draw(self):
        self.play.draw()
        ui.dim(min(0.7, self.t / 40), 0)
        if self.t > 15:
            ui.backdrop(40, 112, line=8)
            ui.ornament_band(40, 50, SCREEN_W - 80, c1=8, c2=2)
            font.text_big(SCREEN_W // 2, 60, "ТЫ ПАЛ В БОЮ", 8, scale=2, shadow=2)
            font.text_center(SCREEN_W // 2, 84, "Но сага ещё не окончена...", 6)
        if self.t >= 30:
            self.menu.draw(SCREEN_W // 2, 104)


# ===================================================================== финал уровня
class VictoryScene(Scene):
    def __init__(self, app, play):
        super().__init__(app)
        self.play = play
        self.t = 0
        self.menu = ui.Menu([("Вернуться в Велеград", True), ("В главное меню", True)])

    def update(self):
        self.t += 1
        if self.t < 40:
            return
        choice = self.menu.update()
        if choice == 0:
            world = self.play.world
            world.sync_state()
            self.app.set_scene(PlayScene(self.app, World(world.state, "town", "start")))
        elif choice == 1:
            self.app.set_scene(TitleScene(self.app))

    def draw(self):
        self.play.world.draw()
        ui.dim(min(0.6, self.t / 50))
        ui.backdrop(30, 128)
        ui.ornament_band(40, 40, SCREEN_W - 80)
        font.text_big(SCREEN_W // 2, 52, "ПУТЬ ПРОЙДЕН", 10, scale=2, shadow=8)
        ui.ornament_band(40, 76, SCREEN_W - 80)
        inv = self.play.world.player.inv
        font.text_center(SCREEN_W // 2, 88, f"Собрано серебра: {inv.silver}", 7)
        done = "boss:jarl" in self.play.world.state.flags
        font.text_center(SCREEN_W // 2, 98, "Ярл повержен. Глава I пройдена." if done
                         else "Пробный уровень завершён.", 6)
        if self.t >= 40:
            self.menu.draw(SCREEN_W // 2, 124)
