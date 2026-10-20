"""Окна поверх игры: меню лавочника, торговля и кузня, отдых у Стелы с распределением очков."""

import pyxel

from . import audio, controls, font, gfx, items, ui
from .config import SCREEN_H, SCREEN_W
from .entities import Stela
from .inventory import MAX_UPGRADE, STAT_HINTS, STAT_NAMES, STATS, xp_needed
from .shops import SHOPS, TAB_NAMES


class Overlay:
    """Окно поверх сцены игры; по закрытию возвращает игру."""

    def __init__(self, app, play):
        self.app = app
        self.play = play
        self.msg = None
        self.msg_col = 10
        self.msg_t = 0

    @property
    def world(self):
        return self.play.world

    @property
    def inv(self):
        return self.play.world.player.inv

    def say(self, text, col=10):
        self.msg, self.msg_col, self.msg_t = text, col, 110

    def close(self):
        self.app.set_scene(self.play)

    def tick(self):
        if self.msg_t > 0:
            self.msg_t -= 1


# ===================================================================== меню лавочника
class NpcMenuScene(Overlay):
    def __init__(self, app, play, npc):
        super().__init__(app, play)
        self.npc = npc
        self.shop = SHOPS[npc.data.shop]
        opts = [("Говорить", True), ("Торговать", True)]
        if "forge" in self.shop.tabs:
            opts.append(("Ковать оружие", True))
        opts.append(("Уйти", True))
        self.menu = ui.Menu(opts, index=1)

    def update(self):
        if controls.pressed("back"):
            self.close()
            return
        choice = self.menu.update()
        if choice is None:
            return
        label = self.menu.options[choice][0]
        if label == "Говорить":
            self.close()
            self.world.start_talk(self.npc)
        elif label == "Торговать":
            self.app.set_scene(TradeScene(self.app, self.play, self.npc.data.shop))
        elif label == "Ковать оружие":
            self.app.set_scene(TradeScene(self.app, self.play, self.npc.data.shop,
                                          tab=self.shop.tabs.index("forge")))
        else:
            self.close()

    def draw(self):
        self.play.draw()
        ui.dim(0.4)
        h = 22 + len(self.menu.options) * 12
        ui.panel(68, 30, 120, h)
        font.text_center(SCREEN_W // 2, 37, self.npc.data.name, 10, shadow=1)
        self.menu.draw(SCREEN_W // 2, 50, spacing=12)


# ===================================================================== торговля и кузня
class TradeScene(Overlay):
    ROWS = 9
    ROW_H = 12
    LIST_X, LIST_Y, LIST_W = 10, 44, 116

    def __init__(self, app, play, shop_id, tab=0):
        super().__init__(app, play)
        self.shop = SHOPS[shop_id]
        self.tab = tab
        self.index = 0
        self.scroll = 0

    @property
    def kind(self):
        return self.shop.tabs[self.tab]

    def entries(self):
        """Список строк вкладки: (вид, предмет, индекс_в_суме или None)."""
        inv = self.inv
        if self.kind == "buy":
            return [("buy", items.get(i), None) for i in self.shop.stock]
        if self.kind == "sell":
            return [("sell", inv.item_at(i), i) for i, c in enumerate(inv.bag) if c]
        rows = []
        weapon = inv.equipped("weapon")
        if weapon:
            rows.append(("forge", weapon, None))
        seen = {weapon.id} if weapon else set()
        for i, c in enumerate(inv.bag):
            item = inv.item_at(i)
            if item and item.kind == "weapon" and item.id not in seen:
                seen.add(item.id)
                rows.append(("forge", item, i))
        return rows

    # ------------------------------------------------------------ логика
    def update(self):
        self.tick()
        if controls.pressed("back"):
            audio.sfx(audio.SELECT)
            self.close()
            return
        rows = self.entries()
        if controls.pressed("left", repeat=True) and self.tab > 0:
            self._switch(-1)
        elif controls.pressed("right", repeat=True) and self.tab < len(self.shop.tabs) - 1:
            self._switch(1)
        elif controls.pressed("up", repeat=True) and self.index > 0:
            self.index -= 1
            audio.sfx(audio.MOVE)
        elif controls.pressed("down", repeat=True) and self.index < len(rows) - 1:
            self.index += 1
            audio.sfx(audio.MOVE)
        elif controls.pressed("confirm") and rows:
            self._act(rows[self.index])
        rows = self.entries()
        self.index = max(0, min(self.index, len(rows) - 1))
        if self.index < self.scroll:
            self.scroll = self.index
        elif self.index >= self.scroll + self.ROWS:
            self.scroll = self.index - self.ROWS + 1

    def _switch(self, step):
        self.tab += step
        self.index = 0
        self.scroll = 0
        audio.sfx(audio.MOVE)

    def _act(self, row):
        kind, item, idx = row
        inv = self.inv
        if kind == "buy":
            if inv.silver < item.price:
                self.say("Не хватает серебра", 8)
                audio.sfx(audio.DENY)
            elif not inv.add(item.id):
                self.say("Сума полна", 8)
                audio.sfx(audio.DENY)
            else:
                inv.silver -= item.price
                self.say("Куплено: " + item.name)
                audio.sfx(audio.COIN)
        elif kind == "sell":
            price = item.sell_price
            inv.remove_at(idx)
            inv.silver += price
            if item.kind == "weapon" and inv.count_of(item.id) == 0 and inv.equipment["weapon"] != item.id:
                inv.upgrades.pop(item.id, None)  # проданная заточка уходит вместе с оружием
            self.say(f"Продано: {item.name} за {price}")
            audio.sfx(audio.COIN)
        else:
            err = inv.upgrade(item.id)
            if err:
                self.say(err, 8)
                audio.sfx(audio.DENY)
            else:
                self.say("Выковано: " + inv.item_name(item))
                audio.sfx(audio.HEAVY)
                self.world.sparks(self.world.player.cx, self.world.player.y, 6)

    # ------------------------------------------------------------ отрисовка
    def draw(self):
        inv = self.inv
        self.play.world.draw()
        ui.dim(0.75)
        ui.panel(4, 8, SCREEN_W - 8, SCREEN_H - 12)
        ui.title_plate(SCREEN_W // 2, 2, self.shop.title)
        # Вкладки.
        x = 12
        for i, tab in enumerate(self.shop.tabs):
            label = TAB_NAMES[tab]
            w = font.text_width(label) + 12
            active = i == self.tab
            pyxel.rect(x, 25, w, 13, 2 if active else 1)
            pyxel.rectb(x, 25, w, 13, 10 if active else 5)
            font.text(x + 6, 28, label, 10 if active else 6)
            x += w + 4
        font.text(SCREEN_W - 12 - font.text_width(f"{font.ARROW_LEFT} {font.ARROW_RIGHT}"), 28,
                  f"{font.ARROW_LEFT} {font.ARROW_RIGHT}", 5)

        rows = self.entries()
        lx, ly = self.LIST_X, self.LIST_Y
        pyxel.rect(lx - 2, ly - 2, self.LIST_W + 4, self.ROWS * self.ROW_H + 3, 0)
        if not rows:
            empty = {"buy": "Товара нет", "sell": "Нечего продать", "forge": "Нет оружия"}[self.kind]
            font.text(lx + 4, ly + 4, empty, 5)
        for n, (kind, item, idx) in enumerate(rows[self.scroll:self.scroll + self.ROWS]):
            i = n + self.scroll
            y = ly + n * self.ROW_H
            if i == self.index:
                pyxel.rect(lx - 1, y - 1, self.LIST_W + 2, self.ROW_H, 2)
                pyxel.rectb(lx - 1, y - 1, self.LIST_W + 2, self.ROW_H, 10)
            gfx.icon(item.icon, lx + 1, y + 1, item.tint)
            name = inv.item_name(item)
            if kind == "sell" and inv.count_at(idx) > 1:
                name += f" x{inv.count_at(idx)}"
            font.text(lx + 12, y + 2, self._fit(name, 80), 7)
            if kind == "forge" and idx is None:
                ui.rhombus(lx + self.LIST_W - 22, y + 5, 2, 10)  # надетое оружие
            if kind == "buy":
                tag, col = str(item.price), (10 if inv.silver >= item.price else 8)
            elif kind == "sell":
                tag, col = str(item.sell_price), 10
            else:
                lvl = inv.upgrade_level(item.id)
                tag, col = (f"+{lvl}" if lvl else "-"), 11
            font.text(lx + self.LIST_W - 2 - font.text_width(tag), y + 2, tag, col)
        if self.scroll > 0:
            font.text(lx + self.LIST_W - 6, ly - 9, font.ARROW_UP, 5)
        if self.scroll + self.ROWS < len(rows):
            font.text(lx + self.LIST_W - 6, ly + self.ROWS * self.ROW_H + 1, font.ARROW_DOWN, 5)

        if rows:
            self._draw_details(rows[self.index])

        # Низ: кошель и подсказка.
        by = SCREEN_H - 26
        pyxel.line(10, by - 3, SCREEN_W - 11, by - 3, 2)
        gfx.icon("coin", 12, by)
        font.text(22, by + 1, str(inv.silver), 7)
        gfx.icon("ore", 52, by)
        font.text(62, by + 1, str(inv.count_of("ore")), 7)
        if self.msg_t > 0:
            font.text_center(160, by + 1, self.msg, self.msg_col)
        hint = {"buy": "Z - купить", "sell": "Z - продать", "forge": "Z - выковать"}[self.kind]
        font.text_center(SCREEN_W // 2, SCREEN_H - 14, hint + "   ESC - уйти", 5)

    @staticmethod
    def _fit(text, width):
        if font.text_width(text) <= width:
            return text
        while text and font.text_width(text + ".") > width:
            text = text[:-1]
        return text + "."

    def _draw_details(self, row):
        kind, item, idx = row
        inv = self.inv
        x, y = 134, 44
        pyxel.rect(x - 2, y - 2, SCREEN_W - x - 8, 118, 0)
        ui.item_box(x, y, 20, item)
        lvl = inv.upgrade_level(item.id) if item.kind == "weapon" else 0
        font.text(x + 24, y + 2, self._fit(item.name, 86), 10)
        font.text(x + 24, y + 11, items.KIND_NAMES.get(item.kind, "") + (f"  +{lvl}" if lvl else ""), 5)
        ty = y + 26
        if kind == "forge":
            lvl = inv.upgrade_level(item.id)
            font.text(x, ty, f"Атака: {inv.item_atk(item)}", 7)
            cost = inv.upgrade_cost(item.id)
            if cost is None or lvl >= MAX_UPGRADE:
                font.text(x, ty + 11, "Наивысшая заточка", 11)
            else:
                silver, ore = cost
                font.text(x, ty + 11, f"Заточка: +{lvl} {font.ARROW_RIGHT} +{lvl + 1}", 11)
                font.text(x, ty + 22, f"Атака станет {inv.item_atk(item) + 1}", 11)
                font.text(x, ty + 36, f"Серебро: {silver}", 10 if inv.silver >= silver else 8)
                have = inv.count_of("ore")
                font.text(x, ty + 47, f"Криц: {ore} (есть {have})", 10 if have >= ore else 8)
            return
        for line in item.stat_lines()[:3]:
            font.text(x, ty, line, 11)
            ty += 10
        # Сравнение с надетым.
        if item.kind in items.SLOTS:
            cur = inv.equipped(item.kind)
            if cur is not None and cur.id != item.id:
                font.text(x, ty + 2, "Надето: " + self._fit(cur.name, 70), 5)
                ty += 12
                for label, a, b in (("Атака", inv.item_atk(cur), item.atk), ("Защита", cur.defense, item.defense),
                                    ("Жизнь", cur.hp, item.hp)):
                    if a != b:
                        font.text(x, ty, f"{label}: {a} {font.ARROW_RIGHT} {b}", 11 if b > a else 8)
                        ty += 10
        for line in font.wrap(item.desc, SCREEN_W - x - 14)[:3]:
            font.text(x, ty + 3, line, 6)
            ty += 9


# ===================================================================== отдых и очки
class RestScene(Overlay):
    def __init__(self, app, play, point):
        super().__init__(app, play)
        self.title = "СТЕЛА ПРЕДКОВ" if isinstance(point, Stela) else "РУННЫЙ КАМЕНЬ"
        self.index = 0
        self.spent = False

    def update(self):
        self.tick()
        inv = self.inv
        n = len(STATS) + 1
        if controls.pressed("up", repeat=True):
            self.index = (self.index - 1) % n
            audio.sfx(audio.MOVE)
        elif controls.pressed("down", repeat=True):
            self.index = (self.index + 1) % n
            audio.sfx(audio.MOVE)
        elif controls.pressed("back") or (controls.pressed("confirm") and self.index == len(STATS)):
            audio.sfx(audio.SELECT)
            if self.spent:
                self.world.save_game()
            self.close()
        elif controls.pressed("confirm"):
            stat = STATS[self.index]
            if inv.spend_point(stat):
                self.spent = True
                p = self.world.player
                p.hp = inv.max_hp
                p.stamina = p.stamina_max
                audio.sfx(audio.CHARGED)
                self.say(f"{STAT_NAMES[stat]}: {inv.stats[stat]}")
            else:
                self.say("Нет свободных очков", 8)
                audio.sfx(audio.DENY)

    def draw(self):
        inv = self.inv
        self.play.world.draw()
        ui.dim(0.65)
        ui.panel(36, 22, SCREEN_W - 72, 150)
        ui.title_plate(SCREEN_W // 2, 15, self.title)
        cx = SCREEN_W // 2
        font.text_center(cx, 40, f"Уровень {inv.level}", 10, shadow=1)
        need = xp_needed(inv.level)
        ui.bar(56, 51, SCREEN_W - 112, 6, inv.xp, need, 11)
        font.text_center(cx, 60, f"опыт {inv.xp} / {need}", 6)
        pts_col = 10 if inv.points and (pyxel.frame_count // 15) % 2 else 7
        font.text_center(cx, 72, f"Свободных очков: {inv.points}", pts_col)
        for i, stat in enumerate(STATS):
            y = 88 + i * 14
            sel = i == self.index
            if sel:
                pyxel.rect(50, y - 3, SCREEN_W - 100, 13, 2)
                pyxel.rectb(50, y - 3, SCREEN_W - 100, 13, 10)
            font.text(58, y, STAT_NAMES[stat], 10 if sel else 7)
            font.text(124, y, str(inv.stats[stat]), 15)
            font.text(140, y, f"({STAT_HINTS[stat]})", 5)
        y = 88 + len(STATS) * 14 + 4
        sel = self.index == len(STATS)
        font.text_center(cx, y, "Встать", 10 if sel else 7, shadow=1)
        if sel:
            ui.rhombus(cx - 24, y + 3, 2, 8)
            ui.rhombus(cx + 23, y + 3, 2, 8)
        summary = f"Жизнь {inv.max_hp}   Атака {inv.attack}   Силы {inv.max_stamina}"
        font.text_center(cx, 150, summary, 6)
        if self.msg_t > 0:
            font.text_center(cx, 160, self.msg, self.msg_col)
