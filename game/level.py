"""Загрузка уровня из текстового файла, тайловые столкновения и отрисовка окружения."""

import math
import random

import pyxel

from . import font, gfx
from .config import SCREEN_H, SCREEN_W, TILE

T_EMPTY = -1
SOLID_TILES = {gfx.TILE_GRASS, gfx.TILE_DIRT, gfx.TILE_STONE, gfx.TILE_LOG,
               gfx.TILE_BOARDWALK, gfx.TILE_FLAGSTONE}

_TILE_CHARS = {"S": gfx.TILE_STONE, "L": gfx.TILE_LOG, "=": gfx.TILE_PLANK, "^": gfx.TILE_SPIKES,
               "_": gfx.TILE_BOARDWALK, "%": gfx.TILE_FLAGSTONE}
_DECOR_TILE_CHARS = {"g": gfx.TILE_TUFT, "m": gfx.TILE_MUSHROOM}
OBJECT_CHARS = set("PRCWDKAUohEXTBIFY")

_TEXT_TOKENS = {
    "{UP}": font.ARROW_UP,
    "{DOWN}": font.ARROW_DOWN,
    "{LEFT}": font.ARROW_LEFT,
    "{RIGHT}": font.ARROW_RIGHT,
}


def _parse_pos(s):
    x, y = s.split(",")
    return int(x), int(y)


def _text(value):
    text = value.strip()
    for token, ch in _TEXT_TOKENS.items():
        text = text.replace(token, ch)
    return text


class Level:
    def __init__(self, path, name):
        self.name = name
        self.meta = {}
        self.chests = {}
        self.signs = {}
        self.exits = {}  # (x, y) -> (локация, точка появления, вид врат)
        self.spawns = {}  # имя -> (x, y)
        self.props = []  # (вид, x, y, ширина)
        self.npcs = []  # (x, y, id)
        rows = []
        section = None
        with open(path, encoding="utf-8") as f:
            for raw in f:
                line = raw.rstrip("\n")
                if section != "map" and (not line.strip() or line.lstrip().startswith("#")):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    section = line[1:-1]
                    continue
                if section == "map":
                    if line.strip():
                        rows.append(line)
                elif section == "props":
                    parts = line.split()
                    x, y = _parse_pos(parts[1])
                    self.props.append((parts[0], x, y, int(parts[2]) if len(parts) > 2 else 0))
                elif "=" in line:
                    key, value = (v.strip() for v in line.split("=", 1))
                    if section == "meta":
                        self.meta[key] = _text(value)
                    elif section == "spawns":
                        self.spawns[key] = _parse_pos(value)
                    elif section == "chests":
                        self.chests[_parse_pos(key)] = [v.strip() for v in value.split(",") if v.strip()]
                    elif section == "signs":
                        self.signs[_parse_pos(key)] = _text(value)
                    elif section == "npcs":
                        x, y = _parse_pos(key)
                        self.npcs.append((x, y, value))
                    elif section == "exits":
                        parts = value.split()
                        target = parts[0]
                        spawn = parts[1] if len(parts) > 1 else None
                        style = parts[2] if len(parts) > 2 else "forest"
                        self.exits[_parse_pos(key)] = (target, spawn, style)

        self.h = len(rows)
        self.w = max(len(r) for r in rows)
        rows = [r.ljust(self.w, ".") for r in rows]
        self.tiles = [[T_EMPTY] * self.w for _ in range(self.h)]
        self.decor = []
        self.objects = []  # (символ, столбец, строка)
        for ty, row in enumerate(rows):
            for tx, ch in enumerate(row):
                if ch == "#":
                    above = rows[ty - 1][tx] if ty > 0 else "."
                    self.tiles[ty][tx] = gfx.TILE_DIRT if above in "#S_%L" else gfx.TILE_GRASS
                elif ch in _TILE_CHARS:
                    self.tiles[ty][tx] = _TILE_CHARS[ch]
                elif ch in _DECOR_TILE_CHARS:
                    self.decor.append((_DECOR_TILE_CHARS[ch], tx, ty))
                elif ch in OBJECT_CHARS:
                    self.objects.append((ch, tx, ty))

        self.pixel_w = self.w * TILE
        self.pixel_h = self.h * TILE
        self.title = self.meta.get("title", name)
        self.subtitle = self.meta.get("subtitle", "")
        self.music = int(self.meta.get("music", 0))
        self.background = Background(self.meta.get("sky", "forest"))

    # ------------------------------------------------------------ запросы
    def tile_at(self, tx, ty):
        if tx < 0 or tx >= self.w:
            return gfx.TILE_STONE  # края мира — стена
        if ty < 0 or ty >= self.h:
            return T_EMPTY
        return self.tiles[ty][tx]

    def is_solid(self, tx, ty):
        return self.tile_at(tx, ty) in SOLID_TILES

    def is_platform(self, tx, ty):
        return self.tile_at(tx, ty) == gfx.TILE_PLANK

    def touches_spikes(self, x, y, w, h):
        """Касается ли прямоугольник острой части кольев (нижние 6 пикселей тайла)."""
        for ty in range(int(y // TILE), int((y + h - 1) // TILE) + 1):
            for tx in range(int(x // TILE), int((x + w - 1) // TILE) + 1):
                if self.tile_at(tx, ty) == gfx.TILE_SPIKES:
                    top = ty * TILE + 2
                    if y + h > top and x + w > tx * TILE + 1 and x < tx * TILE + TILE - 1:
                        return True
        return False

    # ------------------------------------------------------------ отрисовка
    def draw_tiles(self, cam_x):
        tx0 = max(0, int(cam_x // TILE))
        tx1 = min(self.w - 1, int((cam_x + SCREEN_W) // TILE) + 1)
        for ty in range(self.h):
            row = self.tiles[ty]
            for tx in range(tx0, tx1 + 1):
                t = row[tx]
                if t != T_EMPTY:
                    gfx.tile(t, tx * TILE, ty * TILE)
        for t, tx, ty in self.decor:
            if tx0 <= tx <= tx1:
                gfx.tile(t, tx * TILE, ty * TILE)


class Background:
    """Параллакс. style: "forest" — ночь, сияние и ельник; "town" — закат и силуэты городища."""

    def __init__(self, style="forest"):
        self.style = style
        rnd = random.Random(42)
        self.stars = [(rnd.randrange(0, 512), rnd.randrange(0, 90), rnd.randrange(0, 60)) for _ in range(70)]
        self.far = self._ridge(rnd, 512, (48, 72), (92, 108))
        self.near = self._ridge(rnd, 512, (96, 112), (122, 134))
        self.pines = [(rnd.randrange(0, 512), rnd.randrange(10, 22)) for _ in range(46)]
        self.pines.sort()
        self.roofs = []
        x = 0
        while x < 512:
            w = rnd.randrange(14, 30)
            tower = rnd.random() < 0.22
            self.roofs.append((x, w, rnd.randrange(10, 18) + (14 if tower else 0), tower))
            x += w + rnd.randrange(2, 10)

    @staticmethod
    def _ridge(rnd, period, peak_range, valley_range):
        """Ломаная хребта: пики и седловины чередуются, последняя точка совпадает с первой."""
        pts = []
        x = 0
        i = 0
        while x < period:
            pts.append((x, rnd.randrange(*(peak_range if i % 2 == 0 else valley_range))))
            x += rnd.randrange(26, 46)
            i += 1
        if len(pts) % 2:
            pts.pop()
        pts.append((period, pts[0][1]))
        return pts

    def draw(self, cam_x):
        if self.style == "town":
            self._draw_town(cam_x)
        else:
            self._draw_forest(cam_x)

    def _draw_town(self, cam_x):
        t = pyxel.frame_count
        pyxel.cls(1)
        # Закатное небо: сумерки сверху, жар у горизонта.
        for i in range(8):
            pyxel.dither(0.04 + i * 0.12)
            pyxel.rect(0, 36 + i * 8, SCREEN_W, 8, 13)
        pyxel.dither(1.0)
        pyxel.rect(0, 100, SCREEN_W, 60, 13)
        for i in range(4):
            pyxel.dither(0.15 + i * 0.12)
            pyxel.rect(0, 104 + i * 8, SCREEN_W, 8 if i < 3 else 50, 9)
        pyxel.dither(1.0)
        for sx, sy, ph in self.stars[:30]:
            x = (sx - cam_x * 0.03) % 512
            if x < SCREEN_W and sy < 50 and (t // 25 + ph) % 7:
                pyxel.pset(x, sy, 15)
        # Садящееся солнце за горами.
        sun_x = 70 - cam_x * 0.02
        pyxel.circ(sun_x, 100, 13, 9)
        pyxel.circ(sun_x, 100, 10, 10)
        self._draw_ridge(self.far, cam_x * 0.15, 5, snow=True)
        self._draw_ridge(self.near, cam_x * 0.3, 3, snow=False)
        # Дальние крыши и вежи городища.
        offset = cam_x * 0.55
        base = 152
        pyxel.rect(0, base, SCREEN_W, SCREEN_H - base, 1)
        for rx, w, h, tower in self.roofs:
            for rep in (0, 512):
                x = (rx + rep - offset) % 1024 - 40
                if -40 < x < SCREEN_W + 10:
                    pyxel.rect(x, base - h, w, h, 1)
                    if tower:
                        pyxel.tri(x - 2, base - h, x + w / 2, base - h - 16, x + w + 2, base - h, 1)
                    else:
                        pyxel.tri(x - 2, base - h, x + w / 2, base - h - 7, x + w + 2, base - h, 1)
                    if (rx // 3 + t // 90) % 4:
                        pyxel.pset(x + w // 3, base - h + 5, 10)
                    if w > 20:
                        pyxel.pset(x + 2 * w // 3, base - h + 6, 9)

    def _draw_forest(self, cam_x):
        t = pyxel.frame_count
        pyxel.cls(1)
        # Сумеречная полоса у горизонта.
        pyxel.dither(0.3)
        pyxel.rect(0, 92, SCREEN_W, 60, 13)
        pyxel.dither(1.0)
        # Звёзды.
        for sx, sy, ph in self.stars:
            x = (sx - cam_x * 0.03) % 512
            if x < SCREEN_W and (t // 20 + ph) % 9:
                pyxel.pset(x, sy, 15 if ph % 3 else 6)
        # Луна.
        pyxel.circ(206, 30, 10, 7)
        pyxel.circ(210, 27, 9, 1)
        # Северное сияние.
        for i, col in enumerate((11, 12)):
            pyxel.dither(0.45 - i * 0.1)
            for x in range(0, SCREEN_W, 2):
                wx = x + cam_x * 0.08
                y = 26 + i * 8 + math.sin(wx * 0.025 + t * 0.012 + i) * 9 + math.sin(wx * 0.061 - t * 0.02) * 4
                h = 10 + math.sin(wx * 0.04 + t * 0.03) * 5
                pyxel.line(x, y, x, y + h, col)
        pyxel.dither(1.0)
        self._draw_ridge(self.far, cam_x * 0.15, 13, snow=True)
        self._draw_ridge(self.near, cam_x * 0.3, 5, snow=False)
        # Ельник.
        offset = cam_x * 0.5
        base = 150
        pyxel.rect(0, base, SCREEN_W, SCREEN_H - base, 3)
        for px, ph in self.pines:
            for rep in (0, 512):
                x = (px + rep - offset) % 1024 - 32
                if -12 < x < SCREEN_W + 12:
                    self._pine(x, base, ph)

    @staticmethod
    def _draw_ridge(pts, offset, col, snow):
        for rep in range(3):
            shift = rep * 512 - (offset % 512)
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                ax, bx = x0 + shift, x1 + shift
                if bx < 0 or ax > SCREEN_W:
                    continue
                pyxel.tri(ax, y0, bx, y1, ax, 160, col)
                pyxel.tri(bx, y1, bx, 160, ax, 160, col)
            if not snow:
                continue
            # Снежные шапки по склонам каждого пика.
            for i in range(0, len(pts) - 1, 2):
                px, py = pts[i][0] + shift, pts[i][1]
                if not -40 < px < SCREEN_W + 40:
                    continue
                lx, ly = pts[i - 1] if i > 0 else (pts[-2][0] - 512, pts[-2][1])
                rx, ry = pts[i + 1]
                lx += shift
                rx += shift
                k = 0.3
                pyxel.tri(px, py, px + (lx - px) * k, py + (ly - py) * k,
                          px + (rx - px) * k, py + (ry - py) * k, 7)

    @staticmethod
    def _pine(x, base, h):
        pyxel.rect(x - 1, base - 3, 2, 3, 2)
        for i in range(3):
            w = 7 - i * 2
            y = base - 3 - i * h // 4
            pyxel.tri(x, y - h // 2, x - w, y, x + w, y, 3 if i else 1)
