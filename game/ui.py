"""Элементы интерфейса в славянско-скандинавском духе: рамки с узором, меню, полосы."""

import pyxel

from . import audio, controls, font, gfx
from .config import SCREEN_H, SCREEN_W


def dim(alpha=0.6, col=0):
    pyxel.dither(alpha)
    pyxel.rect(0, 0, SCREEN_W, SCREEN_H, col)
    pyxel.dither(1.0)


def backdrop(y, h, line=10):
    """Сплошная тёмная полоса во всю ширину экрана — подложка под крупный текст."""
    pyxel.rect(0, y, SCREEN_W, h, 0)
    pyxel.line(0, y, SCREEN_W, y, line)
    pyxel.line(0, y + h - 1, SCREEN_W, y + h - 1, line)


def rhombus(cx, cy, r, col):
    for i in range(r + 1):
        w = r - i
        pyxel.line(cx - w, cy - i, cx + w, cy - i, col)
        pyxel.line(cx - w, cy + i, cx + w, cy + i, col)


def ornament_band(x, y, w, c1=8, c2=10):
    """Полоса из ромбов, как на вышивке рушника."""
    pyxel.line(x, y - 3, x + w - 1, y - 3, c2)
    pyxel.line(x, y + 3, x + w - 1, y + 3, c2)
    i = 0
    for cx in range(x + 3, x + w - 2, 6):
        rhombus(cx, y, 2, c1 if i % 2 == 0 else c2)
        i += 1


def panel(x, y, w, h, fill=1, border=10, accent=8):
    pyxel.rect(x, y, w, h, fill)
    pyxel.rectb(x, y, w, h, 2)
    pyxel.rectb(x + 1, y + 1, w - 2, h - 2, border)
    pyxel.rectb(x + 2, y + 2, w - 4, h - 4, 2)
    for cx, cy in ((x + 1, y + 1), (x + w - 2, y + 1), (x + 1, y + h - 2), (x + w - 2, y + h - 2)):
        rhombus(cx, cy, 2, accent)
        pyxel.pset(cx, cy, border)


def title_plate(cx, y, text, col=10):
    w = font.text_width(text) + 16
    x = cx - w // 2
    panel(x, y, w, 15, fill=2, border=col, accent=8)
    font.text_center(cx, y + 4, text, col, shadow=1)


def bar(x, y, w, h, value, max_value, col, back=1, border=2, shine=True):
    pyxel.rect(x, y, w, h, back)
    fill = int((w - 2) * max(0, value) / max(1, max_value))
    pyxel.rect(x + 1, y + 1, fill, h - 2, col)
    if shine and fill > 2:
        pyxel.line(x + 1, y + 1, x + fill, y + 1, 15 if col != 15 else 7)
    pyxel.rectb(x, y, w, h, border)


class Menu:
    """Вертикальное меню. options — список (текст, включено)."""

    def __init__(self, options, index=0):
        self.options = options
        self.index = index
        if not self.options[self.index][1]:
            self.move(1, silent=True)

    def move(self, step, silent=False):
        n = len(self.options)
        for _ in range(n):
            self.index = (self.index + step) % n
            if self.options[self.index][1]:
                break
        if not silent:
            audio.sfx(audio.MOVE)

    def update(self):
        """Возвращает индекс выбранного пункта или None."""
        if controls.pressed("up", repeat=True):
            self.move(-1)
        elif controls.pressed("down", repeat=True):
            self.move(1)
        elif controls.pressed("confirm"):
            audio.sfx(audio.SELECT)
            return self.index
        return None

    def draw(self, cx, y, spacing=13, col=7, sel_col=10, off_col=5):
        for i, (label, enabled) in enumerate(self.options):
            yy = y + i * spacing
            selected = i == self.index
            c = sel_col if selected else (col if enabled else off_col)
            font.text_center(cx, yy, label, c, shadow=1)
            if selected:
                half = font.text_width(label) // 2
                bob = (pyxel.frame_count // 10) % 2
                rhombus(cx - half - 8 - bob, yy + 3, 2, 8)
                rhombus(cx + half + 7 + bob, yy + 3, 2, 8)


def item_box(x, y, size, item, count=0, selected=False, highlight=False):
    pyxel.rect(x, y, size, size, 0 if not highlight else 2)
    pyxel.rectb(x, y, size, size, 10 if selected else 5)
    if selected:
        pyxel.rectb(x - 1, y - 1, size + 2, size + 2, 8 if (pyxel.frame_count // 15) % 2 else 10)
    if item:
        off = (size - 16) // 2
        gfx.icon(item.icon, x + off, y + off, item.tint, scale=2)
        if count > 1:
            font.text(x + size - 6, y + size - 8, str(count), 15, shadow=0)
