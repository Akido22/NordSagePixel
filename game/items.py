"""База предметов: читается из data/items.toml."""

from dataclasses import dataclass, field

from . import data
from .gfx import ICON_INDEX

# Слоты экипировки в порядке отображения.
SLOTS = ["weapon", "shield", "helmet", "armor", "amulet"]
KINDS = SLOTS + ["consumable", "material", "rune"]

SLOT_NAMES = {
    "weapon": "Оружие",
    "shield": "Щит",
    "helmet": "Шлем",
    "armor": "Доспех",
    "amulet": "Оберег",
}
KIND_NAMES = dict(SLOT_NAMES, consumable="Припасы", material="Для кузни", rune="Руна")

_TRADE = data.Section("progression.toml", "trade", data.load("progression.toml").get("trade", {}))
SELL_RATE = _TRADE.get("sell_rate", float)


@dataclass(frozen=True)
class Item:
    id: str
    name: str
    kind: str  # слот из SLOTS, "consumable" (припасы), "material" (для кузни), "rune" (чары)
    icon: str
    desc: str
    atk: int = 0
    defense: int = 0
    hp: int = 0
    heal: int = 0
    mana: int = 0  # припасы: сколько маны возвращают
    tint: dict = field(default_factory=dict)
    # Оружие: дальность удара (пикс.), длительность замаха (кадры), расход выносливости.
    reach: int = 0
    swing: int = 0
    stamina: int = 0
    # Щит: (обод, поле, умбон).
    shield_colors: tuple = (2, 4, 6)
    price: int = 0  # цена в лавке; продать можно за SELL_RATE от неё

    @property
    def stackable(self):
        return self.kind in ("consumable", "material")

    @property
    def sell_price(self):
        return max(1, int(self.price * SELL_RATE))

    def stat_lines(self):
        lines = []
        if self.atk:
            lines.append(f"Атака +{self.atk}")
        if self.defense:
            lines.append(f"Защита +{self.defense}")
        if self.hp:
            lines.append(f"Здоровье +{self.hp}")
        if self.heal:
            lines.append(f"Лечит {self.heal}")
        if self.mana:
            lines.append(f"Мана +{self.mana}")
        if self.reach:
            speed = "быстрый" if self.swing <= 16 else "средний" if self.swing <= 22 else "медленный"
            lines.append(f"Удар: {speed}")
        if self.stamina:
            lines.append(f"Силы: {self.stamina}")
        return lines


def _load_items():
    result = {}
    for item_id, sec in data.sections("items.toml"):
        kind = sec.get("kind", str)
        if kind not in KINDS:
            raise data.DataError(f"{sec.where('kind')}: вид «{kind}» неизвестен; можно: {', '.join(KINDS)}")
        icon = sec.get("icon", str)
        if icon not in ICON_INDEX:
            raise data.DataError(f"{sec.where('icon')}: нет иконки «{icon}» (есть: {', '.join(ICON_INDEX)})")
        colors = sec.get("shield_colors", list, [2, 4, 6])
        if len(colors) != 3 or not all(isinstance(c, int) and 0 <= c < 16 for c in colors):
            raise data.DataError(f"{sec.where('shield_colors')}: нужно три номера цвета 0-15")
        item = Item(
            id=item_id,
            name=sec.get("name", str),
            kind=kind,
            icon=icon,
            desc=sec.get("desc", str, ""),
            atk=sec.get("atk", int, 0),
            defense=sec.get("defense", int, 0),
            hp=sec.get("hp", int, 0),
            heal=sec.get("heal", int, 0),
            mana=sec.get("mana", int, 0),
            tint=data.tint(sec, "tint"),
            reach=sec.get("reach", int, 0),
            swing=sec.get("swing", int, 0),
            stamina=sec.get("stamina", int, 0),
            shield_colors=tuple(colors),
            price=sec.get("price", int, 0),
        )
        if kind == "weapon" and (item.reach <= 0 or item.swing <= 0):
            raise data.DataError(f"{sec.where()}: у оружия должны быть reach и swing больше нуля")
        sec.check_unknown()
        result[item_id] = item
    return result


ITEMS = _load_items()


def get(item_id):
    return ITEMS[item_id]


def check_ids(ids, where):
    """Проверка ссылок на предметы из других файлов данных."""
    for item_id in ids:
        if item_id not in ITEMS:
            raise data.DataError(f"{where}: нет предмета «{item_id}» в data/items.toml")
