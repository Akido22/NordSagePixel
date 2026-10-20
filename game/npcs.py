"""Жители: облик и реплики (data/npcs.toml). Расставляются в разделе [npcs] файла уровня."""

from dataclasses import dataclass
from types import SimpleNamespace

from . import data
from .shops import SHOPS

TORSOS = ("hero_torso_plain", "hero_torso_shirt", "hero_torso_leather", "hero_torso_mail", "hero_torso_dress")
HEADS = ("hero_head_male", "hero_head_female")
HELMETS = ("hero_helmet_cap", "hero_helmet_shishak", "hero_helmet_crown")
HELD = ("knife", "sword", "axe", "spear", "hammer")


@dataclass(frozen=True)
class NpcDef:
    name: str
    lines: list
    look: tuple  # слои спрайтов: ((лист, перекраска), ...)
    held: object = None  # предмет в руке (как оружие героя)
    facing: int = 1
    shop: str = None  # id лавки из shops.toml, если житель торгует


def _choice(sec, table, key, options, default):
    value = table.get(key, default)
    if value is not None and value not in options:
        raise data.DataError(f"{sec.where('look')}: {key} = «{value}» — нет такого слоя; можно: {', '.join(options)}")
    return value


def _look(sec):
    table = sec.get("look", dict, {})
    sub = data.Section(sec.filename, sec.name + ".look", table)
    torso = _choice(sec, table, "torso", TORSOS, "hero_torso_plain")
    head = _choice(sec, table, "head", HEADS, "hero_head_male")
    helmet = _choice(sec, table, "helmet", HELMETS, None)
    for key in ("torso", "head", "helmet"):
        sub.used.add(key)
    layers = [("hero_legs", data.tint(sub, "legs_tint") or None),
              (torso, data.tint(sub, "torso_tint") or None),
              (head, data.tint(sub, "head_tint") or None)]
    if helmet:
        layers.append((helmet, data.tint(sub, "helmet_tint") or None))
    sub.check_unknown()
    return tuple(layers)


def _held(sec):
    table = sec.get("held", dict, None)
    if table is None:
        return None
    sub = data.Section(sec.filename, sec.name + ".held", table)
    icon = sub.get("icon", str)
    if icon not in HELD:
        raise data.DataError(f"{sub.where('icon')}: «{icon}» — можно: {', '.join(HELD)}")
    held = SimpleNamespace(icon=icon, tint=data.tint(sub, "tint"))
    sub.check_unknown()
    return held


def _load():
    raw = data.load("npcs.toml")
    hero = raw.pop("hero_name", "Ратмир")
    result = {}
    for npc_id, sec in data.sections("npcs.toml", raw):
        lines = [str(line).replace("{hero}", hero) for line in sec.get("lines", list)]
        facing = sec.get("facing", int, 1)
        if facing not in (1, -1):
            raise data.DataError(f"{sec.where('facing')}: только 1 (вправо) или -1 (влево)")
        result[npc_id] = NpcDef(
            name=sec.get("name", str),
            lines=lines,
            look=_look(sec),
            held=_held(sec),
            facing=facing,
            shop=sec.get("shop", str, None),
        )
        shop = result[npc_id].shop
        if shop is not None and shop not in SHOPS:
            raise data.DataError(f"{sec.where('shop')}: нет лавки «{shop}» в data/shops.toml")
        sec.check_unknown()
    return hero, result


HERO_NAME, NPCS = _load()
