"""Состояние похода, общее для всех локаций: сума, здоровье, сундуки, находки, точка сохранения."""

from . import items
from .inventory import Inventory

START_LEVEL = "town"


class GameState:
    def __init__(self):
        self.inventory = Inventory.starting()
        self.hp = self.inventory.max_hp
        self.collected = set()  # "локация:uid" подобранных предметов с карты
        self.chests = {}  # "локация:uid" -> оставшаяся добыча
        self.save_point = None  # "локация:uid" последнего камня/стелы
        self.level = START_LEVEL
        self.spawn = "start"
        self.pos = None  # точное положение героя (из сохранения)

    @staticmethod
    def key(level, uid):
        return f"{level}:{uid}"

    def to_save(self, level, pos):
        return {
            "level": level,
            "pos": list(pos),
            "hp": self.hp,
            "inventory": self.inventory.to_dict(),
            "collected": sorted(self.collected),
            "chests": self.chests,
            "save_point": self.save_point,
        }

    @classmethod
    def from_save(cls, data):
        st = cls()
        st.inventory = Inventory.from_dict(data.get("inventory", {}))
        st.hp = max(1, min(st.inventory.max_hp, int(data.get("hp", st.inventory.max_hp))))
        st.collected = set(data.get("collected", []))
        st.chests = {k: [i for i in v if i in items.ITEMS] for k, v in data.get("chests", {}).items()}
        st.save_point = data.get("save_point")
        st.level = data.get("level", START_LEVEL)
        st.pos = tuple(data["pos"]) if data.get("pos") else None
        st.spawn = None
        return st
