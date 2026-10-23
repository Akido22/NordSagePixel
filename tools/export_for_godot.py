"""Выгрузка графики, шрифта и звуков Pyxel-версии в проект Godot.

    python tools/export_for_godot.py D:/путь/к/godot-проекту

Всё рисуется теми же функциями, что и в игре, и сохраняется в PNG в масштабе
SCALE (тайл 8 px -> 16 px). Прозрачность: каждый кадр рисуется дважды, на
разном фоне, — пиксель, совпавший в обоих, принадлежит объекту (так чёрный
цвет 0 внутри рисунка не пропадает).
Анимации — горизонтальные ленты кадров; описание (размер кадра, число кадров,
скорость, точка привязки) — в соседнем JSON.
"""

import ctypes
import json
import math
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pyxel  # noqa: E402
from PIL import Image  # noqa: E402

from game import audio, config, entities, font, gfx, level, props  # noqa: E402

SCALE = 2
W, H = 512, 256  # холст выгрузки
BG_A, BG_B = 0, 15  # два фона для выделения прозрачности
TRANSPARENT = (0, 0, 0, 0)
RGB = [((c >> 16) & 255, (c >> 8) & 255, c & 255, 255) for c in config.PALETTE]


class _Clock:
    """Подменяет pyxel в модулях рисования, чтобы задавать номер кадра."""

    frame_count = 0

    def __getattr__(self, name):
        return getattr(pyxel, name)


CLOCK = _Clock()
for _mod in (entities, props, level):
    _mod.pyxel = CLOCK


# ------------------------------------------------------------ холст
def _screen_bytes():
    ptr = pyxel.screen.data_ptr()
    return bytes(ctypes.cast(ptr, ctypes.POINTER(ctypes.c_uint8 * (W * H))).contents)


def _render(draw, t):
    CLOCK.frame_count = t
    out = []
    for bg in (BG_A, BG_B):
        pyxel.cls(bg)
        draw()
        pyxel.pal()
        pyxel.dither(1.0)
        out.append(_screen_bytes())
    return out


def _bbox(frames):
    x0, y0, x1, y1 = W, H, -1, -1
    for a, b in frames:
        for i in range(W * H):
            if a[i] == b[i]:
                x, y = i % W, i // W
                x0, y0, x1, y1 = min(x0, x), min(y0, y), max(x1, x), max(y1, y)
    return x0, y0, x1 + 1, y1 + 1


def _to_image(frame, box):
    a, b = frame
    x0, y0, x1, y1 = box
    img = Image.new("RGBA", (x1 - x0, y1 - y0), TRANSPARENT)
    px = img.load()
    for y in range(y0, y1):
        row = y * W
        for x in range(x0, x1):
            if a[row + x] == b[row + x]:
                px[x - x0, y - y0] = RGB[a[row + x]]
    return img


def _scaled(img):
    return img.resize((img.width * SCALE, img.height * SCALE), Image.NEAREST)


def _strip(images):
    fw, fh = images[0].size
    sheet = Image.new("RGBA", (fw * len(images), fh), TRANSPARENT)
    for i, im in enumerate(images):
        sheet.paste(im, (i * fw, 0))
    return sheet


def capture(draw, anchor, frames=1, step=1):
    """Рисует кадры 0, step, 2*step...; возвращает ленту и описание.
    anchor — точка на холсте, к которой объект привязан в уровне."""
    raw = [_render(draw, i * step) for i in range(frames)]
    box = _bbox(raw)
    images = [_scaled(_to_image(f, box)) for f in raw]
    meta = {
        "frame_w": images[0].width,
        "frame_h": images[0].height,
        "frames": frames,
        "fps": round(config.FPS / step, 3),
        "anchor": [(anchor[0] - box[0]) * SCALE, (anchor[1] - box[1]) * SCALE],
    }
    return _strip(images), meta


# ------------------------------------------------------------ выгрузка
class Exporter:
    def __init__(self, out):
        self.out = out

    def path(self, *parts):
        p = os.path.join(self.out, *parts)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        return p

    def save_json(self, data, *parts):
        with open(self.path(*parts), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)

    # -------------------------------------------------------- тайлы и иконки
    def tiles(self):
        bank = pyxel.images[gfx.SPRITE_BANK]
        names = ["grass", "dirt", "stone", "plank", "spikes", "log", "tuft", "mushroom", "boardwalk", "flagstone"]
        sheet = Image.new("RGBA", (8 * len(names), 8), TRANSPARENT)
        px = sheet.load()
        for i in range(len(names)):
            for y in range(8):
                for x in range(8):
                    c = bank.pget(i * 8 + x, y)
                    if c:
                        px[i * 8 + x, y] = RGB[c]
        _scaled(sheet).save(self.path("assets", "tiles", "tiles.png"))
        self.save_json({
            "tile": 8 * SCALE,
            "order": names,
            "solid": [names[t] for t in sorted(level.SOLID_TILES)],
            "one_way": ["plank"],
            "hazard": ["spikes"],
            "decor": ["tuft", "mushroom"],
        }, "assets", "tiles", "tiles.json")

    def icons(self):
        bank = pyxel.images[gfx.SPRITE_BANK]
        names = list(gfx.ICON_INDEX)
        sheet = Image.new("RGBA", (8 * len(names), 8), TRANSPARENT)
        px = sheet.load()
        for i in range(len(names)):
            for y in range(8):
                for x in range(8):
                    c = bank.pget(i * 8 + x, gfx.ICON_Y + y)
                    if c:
                        px[i * 8 + x, y] = RGB[c]
        _scaled(sheet).save(self.path("assets", "sprites", "icons.png"))
        self.save_json({"cell": 8 * SCALE, "order": names}, "assets", "sprites", "icons.json")

    # -------------------------------------------------------- объекты и постройки
    def objects(self):
        tx, ty = 24, 27  # тайл, к низу-левому углу которого привязан объект
        anchor = (tx * config.TILE, (ty + 1) * config.TILE)

        def with_attr(obj, **attrs):
            for k, v in attrs.items():
                setattr(obj, k, v)
            return obj

        items = {
            "runestone": (entities.Runestone(tx, ty), 1, 1),
            "runestone_active": (with_attr(entities.Runestone(tx, ty), active=True), 20, 4),
            "chest_closed": (entities.Chest(tx, ty, []), 1, 1),
            "chest_open": (with_attr(entities.Chest(tx, ty, []), opened=True), 1, 1),
            "sign": (entities.Sign(tx, ty, ""), 1, 1),
            "signpost_left": (entities.EdgeExit(1, ty, "", None), 1, 1),
            "signpost_right": (entities.EdgeExit(tx, ty, "", None), 1, 1),
            "gate_forest": (entities.Gate(tx, ty, style="forest"), 16, 8),
            "gate_town": (entities.Gate(tx, ty, style="town"), 16, 5),
            "gate_barrow": (entities.Gate(tx, ty, style="barrow"), 16, 8),
            "gate_barrow_locked": (with_attr(entities.Gate(tx, ty, style="barrow"), locked=True), 1, 1),
            "stela": (entities.Stela(tx, ty), 1, 1),
            "stela_active": (with_attr(entities.Stela(tx, ty), active=True), 21, 5),
            "decor_birch": (entities.Decor("B", tx, ty), 1, 1),
            "decor_idol": (entities.Decor("I", tx, ty), 1, 1),
            "decor_fire": (entities.Decor("F", tx, ty), 15, 2),
        }
        meta = {}
        for name, (obj, frames, step) in items.items():
            a = anchor
            if name == "signpost_left":
                a = (1 * config.TILE, anchor[1])
            sheet, info = capture(obj.draw, a, frames, step)
            sheet.save(self.path("assets", "sprites", "objects", name + ".png"))
            meta[name] = info
        # Оброненное серебро привязано к своей середине низа.
        silver = entities.LostSilver(anchor[0] - 5, anchor[1], 0)
        sheet, info = capture(silver.draw, (anchor[0], anchor[1]), 16, 4)
        sheet.save(self.path("assets", "sprites", "objects", "lost_silver.png"))
        meta["lost_silver"] = info
        self.save_json(meta, "assets", "sprites", "objects", "objects.json")

    def props(self):
        tx, ty = 8, 27
        anchor = (tx * config.TILE, (ty + 1) * config.TILE)
        animated = {"izba": (7, 40), "longhouse": (7, 40), "forge": (24, 2), "banner": (21, 5),
                    "lantern": (3, 5), "oak": (16, 8), "torch": (3, 4)}
        widths = {kind: {props._DEFAULT_W.get(kind, 2)} for kind in props.KINDS}
        for fn in os.listdir(config.LEVELS_DIR):
            lvl = level.Level(os.path.join(config.LEVELS_DIR, fn), fn[:-4])
            for kind, _x, _y, w in lvl.props:
                if w:
                    widths[kind].add(w)
        meta = {}
        for kind in sorted(props.KINDS):
            frames, step = animated.get(kind, (1, 1))
            for w in sorted(widths[kind]):
                prop = props.Prop(kind, tx, ty, w)
                sheet, info = capture(prop.draw, anchor, frames, step)
                name = f"{kind}_{w}"
                sheet.save(self.path("assets", "sprites", "props", name + ".png"))
                meta[name] = info
        self.save_json(meta, "assets", "sprites", "props", "props.json")

    # -------------------------------------------------------- фоны
    def backgrounds(self):
        bg = level.Background("forest")
        period = 512
        meta = {}

        def _opaque(a, box):
            x0, y0, x1, y1 = box
            img = Image.new("RGBA", (x1 - x0, y1 - y0))
            px = img.load()
            for y in range(y0, y1):
                for x in range(x0, x1):
                    px[x, y] = RGB[a[y * W + x]]
            return img

        def layer(style, name, draw, parallax, opaque=False):
            raw = _render(draw, 0)
            box = (0, 0, period, config.SCREEN_H)
            img = _opaque(raw[0], box) if opaque else _to_image(raw, box)
            _scaled(img).save(self.path("assets", "backgrounds", style, name + ".png"))
            meta.setdefault(style, []).append({"layer": name, "parallax": parallax, "width": period * SCALE})

        sw = config.SCREEN_W
        level.SCREEN_W = period  # циклы фона рисуют всю ленту разом

        # --- лес
        def forest_sky():
            pyxel.rect(0, 0, period, config.SCREEN_H, 1)
            pyxel.dither(0.3)
            pyxel.rect(0, 92, period, 60, 13)
            pyxel.dither(1.0)
            pyxel.circ(206, 30, 10, 7)
            pyxel.circ(210, 27, 9, 1)

        def stars(count, max_y=999):
            def draw():
                for sx, sy, ph in bg.stars[:count]:
                    if sy < max_y:
                        pyxel.pset(sx, sy, 15 if ph % 3 else 6)
            return draw

        def aurora():
            for i, col in enumerate((11, 12)):
                pyxel.dither(0.45 - i * 0.1)
                for x in range(0, period, 2):
                    y = 26 + i * 8 + math.sin(x * 0.025 + i) * 9 + math.sin(x * 0.061) * 4
                    h = 10 + math.sin(x * 0.04) * 5
                    pyxel.line(x, y, x, y + h, col)
            pyxel.dither(1.0)

        def ridge(pts, col, snow):
            return lambda: level.Background._draw_ridge(pts, 0, col, snow)

        def pines():
            base = 150
            pyxel.rect(0, base, period, config.SCREEN_H - base, 3)
            for px_, ph in bg.pines:
                for rep in (-period, 0, period):
                    level.Background._pine(px_ + rep, base, ph)

        layer("forest", "sky", forest_sky, 0.0, opaque=True)
        layer("forest", "stars", stars(70), 0.03)
        layer("forest", "aurora", aurora, 0.08)
        layer("forest", "far", ridge(bg.far, 13, True), 0.15)
        layer("forest", "near", ridge(bg.near, 5, False), 0.3)
        layer("forest", "pines", pines, 0.5)

        # --- город
        def town_sky():
            pyxel.rect(0, 0, period, config.SCREEN_H, 1)
            for i in range(8):
                pyxel.dither(0.04 + i * 0.12)
                pyxel.rect(0, 36 + i * 8, period, 8, 13)
            pyxel.dither(1.0)
            pyxel.rect(0, 100, period, 60, 13)
            for i in range(4):
                pyxel.dither(0.15 + i * 0.12)
                pyxel.rect(0, 104 + i * 8, period, 8 if i < 3 else 50, 9)
            pyxel.dither(1.0)
            pyxel.circ(70, 100, 13, 9)
            pyxel.circ(70, 100, 10, 10)

        def roofs():
            base = 152
            pyxel.rect(0, base, period, config.SCREEN_H - base, 1)
            for rx, w, h, tower in bg.roofs:
                for rep in (-period, 0, period):
                    x = rx + rep
                    pyxel.rect(x, base - h, w, h, 1)
                    peak = 16 if tower else 7
                    pyxel.tri(x - 2, base - h, x + w / 2, base - h - peak, x + w + 2, base - h, 1)
                    if (rx // 3) % 4:
                        pyxel.pset(x + w // 3, base - h + 5, 10)
                    if w > 20:
                        pyxel.pset(x + 2 * w // 3, base - h + 6, 9)

        layer("town", "sky", town_sky, 0.0, opaque=True)
        layer("town", "stars", stars(30, 50), 0.03)
        layer("town", "far", ridge(bg.far, 5, True), 0.15)
        layer("town", "near", ridge(bg.near, 3, False), 0.3)
        layer("town", "roofs", roofs, 0.55)

        # --- курган: кладка повторяется через 18*28 = 504 px
        wall_period = 504

        def wall():
            pyxel.rect(0, 0, period, config.SCREEN_H, 0)
            for row in range(0, config.SCREEN_H, 14):
                shift = 9 if (row // 14) % 2 else 0
                for i in range(-1, wall_period // 18 + 1):
                    bx = i * 18 + shift
                    seed = (i % 28) + row * 7
                    col = 1 if seed % 9 else 13
                    pyxel.rect(bx + 1, row + 1, 16, 12, col)
                    if seed % 11 == 0:
                        pyxel.line(bx + 8, row + 3, bx + 8, row + 10, 5)
                        pyxel.line(bx + 8, row + 4, bx + 11, row + 7, 5)
            pyxel.dither(0.5)
            pyxel.rect(0, 0, period, config.SCREEN_H, 0)
            pyxel.dither(1.0)

        def roots():
            for i in range(0, period, 37):
                for rep in (-period, 0):
                    x = i + rep + 40
                    h = 18 + (i * 7) % 26
                    pyxel.line(x, 0, x + 2, h, 2)
                    pyxel.line(x + 2, h, x + 1, h + 6, 2)

        raw = _render(wall, 0)
        _scaled(_opaque(raw[0], (0, 0, wall_period, config.SCREEN_H))).save(
            self.path("assets", "backgrounds", "barrow", "wall.png"))
        meta["barrow"] = [{"layer": "wall", "parallax": 0.6, "width": wall_period * SCALE}]
        layer("barrow", "roots", roots, 0.8)

        level.SCREEN_W = sw
        self.save_json(meta, "assets", "backgrounds", "backgrounds.json")

    # -------------------------------------------------------- персонажи
    def sprites(self):
        src = os.path.join(ROOT, "assets", "sprites")
        dst = self.path("assets", "sprites", "characters", "x")
        dst = os.path.dirname(dst)
        key = RGB[0][:3]
        for fn in sorted(os.listdir(src)):
            if not fn.endswith(".png"):
                continue
            img = Image.open(os.path.join(src, fn)).convert("RGBA")
            px = img.load()
            for y in range(img.height):
                for x in range(img.width):
                    if px[x, y][:3] == key:
                        px[x, y] = TRANSPARENT
            _scaled(img).save(os.path.join(dst, fn))
        # Точки привязки и размеры — в пикселях нового масштаба.
        with open(os.path.join(src, "humanoid.json"), encoding="utf-8") as f:
            hum = json.load(f)
        hum["frame_w"] *= SCALE
        hum["frame_h"] *= SCALE
        for fr in hum["frames"]:
            for k in ("hand", "back", "head"):
                fr[k] = [round(v * SCALE, 2) for v in fr[k]]
        self.save_json(hum, "assets", "sprites", "characters", "humanoid.json")
        with open(os.path.join(src, "wolf.json"), encoding="utf-8") as f:
            wolf = json.load(f)
        wolf["frame_w"] *= SCALE
        wolf["frame_h"] *= SCALE
        self.save_json(wolf, "assets", "sprites", "characters", "wolf.json")
        with open(os.path.join(src, "weapons.json"), encoding="utf-8") as f:
            weapons = json.load(f)
        weapons["cell"] = [v * SCALE for v in weapons["cell"]]
        weapons["grip"] = [v * SCALE for v in weapons["grip"]]
        self.save_json(weapons, "assets", "sprites", "characters", "weapons.json")
        shutil.copy(os.path.join(src, "palette.gpl"), self.path("assets", "sprites", "palette.gpl"))

    # -------------------------------------------------------- шрифт
    def font(self):
        """Растровый шрифт BMFont (.fnt + .png): белые глифы, цвет задаёт Godot."""
        glyphs = list(font._RAW.items())
        per_row = 16
        cell = font.CELL
        rows = (len(glyphs) + per_row - 1) // per_row
        img = Image.new("RGBA", (per_row * cell, rows * cell), TRANSPARENT)
        px = img.load()
        chars = {}
        for i, (ch, data) in enumerate(glyphs):
            u, v = (i % per_row) * cell, (i // per_row) * cell
            for y, row in enumerate(data):
                for x, c in enumerate(row):
                    if c == "#":
                        px[u + x, v + y] = (255, 255, 255, 255)
            chars[ord(ch)] = (u, v, len(data[0]))
        # Строчные и похожие латинские буквы рисуются глифами прописных.
        extra = {}
        for ch, (u, v, w) in list(chars.items()):
            low = chr(ch).lower()
            if low != chr(ch) and ord(low) not in chars:
                extra[ord(low)] = (u, v, w)
        for src, dst in font._ALIASES.items():
            if ord(dst) in chars:
                extra.setdefault(ord(src), chars[ord(dst)])
                low = src.lower()
                if low != src:
                    extra.setdefault(ord(low), chars[ord(dst)])
        # Стрелки в Pyxel — служебные .., в Godot — обычные символы.
        for arrow, code in (("↑", font.ARROW_UP), ("↓", font.ARROW_DOWN),
                            ("←", font.ARROW_LEFT), ("→", font.ARROW_RIGHT)):
            extra[ord(arrow)] = chars[ord(code)]
        chars.update(extra)
        img.save(self.path("assets", "fonts", "nord_font.png"))
        lines = [
            'info face="NordSaga" size=%d bold=0 italic=0 charset="" unicode=1 stretchH=100 smooth=0 aa=1 '
            'padding=0,0,0,0 spacing=1,1 outline=0' % font.LINE_H,
            "common lineHeight=%d base=%d scaleW=%d scaleH=%d pages=1 packed=0"
            % (font.LINE_H, font.GLYPH_H, img.width, img.height),
            'page id=0 file="nord_font.png"',
            "chars count=%d" % len(chars),
        ]
        for code in sorted(chars):
            u, v, w = chars[code]
            lines.append("char id=%d x=%d y=%d width=%d height=%d xoffset=0 yoffset=0 xadvance=%d page=0 chnl=15"
                         % (code, u, v, w, font.GLYPH_H, w + font.SPACING))
        with open(self.path("assets", "fonts", "nord_font.fnt"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    # -------------------------------------------------------- звук
    def sounds(self):
        names = {v: k.lower() for k, v in vars(audio).items()
                 if k.isupper() and isinstance(v, int) and k not in ("SFX_CHANNEL", "FOREST", "TOWN", "BOSS")}
        for idx, name in sorted(names.items()):
            snd = pyxel.sounds[idx]
            snd.save(self.path("assets", "audio", "sfx", name + ".wav"), snd.total_sec())
        for idx, name in ((audio.FOREST, "forest"), (audio.TOWN, "town"), (audio.BOSS, "boss")):
            music = pyxel.musics[idx]
            sec = max(sum(pyxel.sounds[s].total_sec() for s in seq) for seq in music.seqs if len(seq))
            path = self.path("assets", "audio", "music", name + ".wav")
            music.save(path, sec)
            _loop_import(path)


def _loop_import(path):
    """Настройки импорта Godot: музыка зациклена."""
    with open(path + ".import", "w", encoding="utf-8") as f:
        f.write('[remap]\n\nimporter="wav"\ntype="AudioStreamWAV"\n\n'
                "[params]\n\nedit/loop_mode=2\nedit/loop_begin=0\nedit/loop_end=-1\n")


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    out = os.path.abspath(sys.argv[1])
    if not os.path.isfile(os.path.join(out, "project.godot")):
        sys.exit(f"{out}: это не проект Godot (нет project.godot)")
    pyxel.init(W, H, title="export", fps=config.FPS)
    pyxel.colors[:] = config.PALETTE
    font.init()
    gfx.init()
    audio.init()
    ex = Exporter(out)
    for step in (ex.tiles, ex.icons, ex.objects, ex.props, ex.backgrounds, ex.sprites, ex.font, ex.sounds):
        step()
        print("готово:", step.__name__)
    pyxel.quit()


if __name__ == "__main__":
    main()
