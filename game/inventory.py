"""Сума (инвентарь) и снаряжение героя."""

from . import items

BAG_COLS = 6
BAG_ROWS = 4
BAG_SIZE = BAG_COLS * BAG_ROWS
MAX_STACK = 9

BASE_HP = 10
BASE_ATK = 1
BASE_DEF = 0


class Inventory:
    def __init__(self):
        self.bag = [None] * BAG_SIZE  # каждый элемент: [item_id, count] или None
        self.equipment = {slot: None for slot in items.SLOTS}
        self.silver = 0

    # ------------------------------------------------------------ сума
    def add(self, item_id, count=1):
        """Кладёт предмет в суму. Возвращает False, если места нет."""
        item = items.get(item_id)
        if item.stackable:
            for cell in self.bag:
                if cell and cell[0] == item_id and cell[1] + count <= MAX_STACK:
                    cell[1] += count
                    return True
        for i, cell in enumerate(self.bag):
            if cell is None:
                self.bag[i] = [item_id, count]
                return True
        return False

    def remove_at(self, index, count=1):
        cell = self.bag[index]
        if cell is None:
            return
        cell[1] -= count
        if cell[1] <= 0:
            self.bag[index] = None

    def item_at(self, index):
        cell = self.bag[index]
        return items.get(cell[0]) if cell else None

    def count_at(self, index):
        cell = self.bag[index]
        return cell[1] if cell else 0

    def first_consumable(self):
        """Индекс самого слабого лечащего предмета (чтобы зря не тратить мёд)."""
        best = None
        for i, cell in enumerate(self.bag):
            if cell:
                item = items.get(cell[0])
                if item.heal and (best is None or item.heal < self.item_at(best).heal):
                    best = i
        return best

    # ------------------------------------------------------------ снаряжение
    def equipped(self, slot):
        item_id = self.equipment.get(slot)
        return items.get(item_id) if item_id else None

    def equip_from_bag(self, index):
        """Надевает предмет из сумы; снятый предмет встаёт на его место."""
        item = self.item_at(index)
        if item is None or item.kind not in self.equipment:
            return False
        previous = self.equipment[item.kind]
        self.equipment[item.kind] = item.id
        self.bag[index] = [previous, 1] if previous else None
        return True

    def unequip(self, slot):
        item_id = self.equipment.get(slot)
        if not item_id:
            return False
        for i, cell in enumerate(self.bag):
            if cell is None:
                self.bag[i] = [item_id, 1]
                self.equipment[slot] = None
                return True
        return False

    # ------------------------------------------------------------ показатели
    def _sum(self, attr):
        return sum(getattr(it, attr) for it in (self.equipped(s) for s in items.SLOTS) if it)

    @property
    def max_hp(self):
        return BASE_HP + self._sum("hp")

    @property
    def attack(self):
        return BASE_ATK + self._sum("atk")

    @property
    def defense(self):
        return BASE_DEF + self._sum("defense")

    # ------------------------------------------------------------ сохранение
    def to_dict(self):
        return {"bag": self.bag, "equipment": self.equipment, "silver": self.silver}

    @classmethod
    def from_dict(cls, data):
        inv = cls()
        for i, cell in enumerate(data.get("bag", [])[:BAG_SIZE]):
            if cell and cell[0] in items.ITEMS:
                inv.bag[i] = [cell[0], int(cell[1])]
        for slot, item_id in data.get("equipment", {}).items():
            if slot in inv.equipment and item_id in items.ITEMS:
                inv.equipment[slot] = item_id
        inv.silver = int(data.get("silver", 0))
        return inv

    @classmethod
    def starting(cls):
        inv = cls()
        inv.equipment["weapon"] = "knife"
        inv.equipment["armor"] = "shirt"
        inv.add("bread", 2)
        return inv
